package image

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"

	"github.com/geekjourneyx/md2wechat-skill/internal/config"
)

// VolcengineProvider Volcengine Ark image generation provider.
type VolcengineProvider struct {
	apiKey       string
	baseURL      string
	model        string
	size         string
	outputFormat string
	client       *http.Client
}

// NewVolcengineProvider creates a Volcengine Ark provider.
func NewVolcengineProvider(cfg *config.Config) (*VolcengineProvider, error) {
	model := cfg.ImageModel
	if model == "" {
		model = DefaultProviderModel("volcengine")
	}

	size := cfg.ImageSize
	if size == "" {
		size = "2K"
	}

	baseURL := cfg.ImageAPIBase
	if baseURL == "" {
		baseURL = DefaultProviderBaseURL("volcengine")
	}
	baseURL = strings.TrimRight(baseURL, "/")

	return &VolcengineProvider{
		apiKey:       cfg.ImageAPIKey,
		baseURL:      baseURL,
		model:        model,
		size:         size,
		outputFormat: "png",
		client: &http.Client{
			Timeout: 120 * time.Second,
		},
	}, nil
}

// Name returns the provider name.
func (p *VolcengineProvider) Name() string {
	return "Volcengine"
}

// Generate creates an image via Volcengine Ark.
func (p *VolcengineProvider) Generate(ctx context.Context, prompt string) (*GenerateResult, error) {
	reqBody := map[string]any{
		"model":         p.model,
		"prompt":        prompt,
		"size":          p.size,
		"output_format": p.outputFormat,
		"watermark":     false,
	}

	jsonData, err := json.Marshal(reqBody)
	if err != nil {
		return nil, &GenerateError{
			Provider: p.Name(),
			Code:     "marshal_error",
			Message:  "请求构造失败",
			Original: err,
		}
	}

	req, err := http.NewRequestWithContext(ctx, "POST", p.baseURL+"/images/generations", bytes.NewBuffer(jsonData))
	if err != nil {
		return nil, &GenerateError{
			Provider: p.Name(),
			Code:     "request_error",
			Message:  "创建请求失败",
			Original: err,
		}
	}

	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", "Bearer "+p.apiKey)

	resp, err := p.client.Do(req)
	if err != nil {
		return nil, &GenerateError{
			Provider: p.Name(),
			Code:     "network_error",
			Message:  "网络请求失败，请检查网络连接",
			Hint:     "确认网络连接正常，API 地址正确",
			Original: err,
		}
	}
	defer func() {
		_ = resp.Body.Close()
	}()

	if resp.StatusCode != http.StatusOK {
		return nil, p.handleErrorResponse(resp)
	}

	var result struct {
		Model string `json:"model"`
		Data  []struct {
			URL  string `json:"url"`
			Size string `json:"size,omitempty"`
		} `json:"data"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return nil, &GenerateError{
			Provider: p.Name(),
			Code:     "decode_error",
			Message:  "响应解析失败",
			Original: err,
		}
	}

	if len(result.Data) == 0 || result.Data[0].URL == "" {
		return nil, &GenerateError{
			Provider: p.Name(),
			Code:     "no_image",
			Message:  "未生成图片",
			Hint:     "提示词可能不符合内容政策，请尝试修改提示词",
		}
	}

	model := p.model
	if result.Model != "" {
		model = result.Model
	}

	size := p.size
	if result.Data[0].Size != "" {
		size = result.Data[0].Size
	}

	return &GenerateResult{
		URL:   result.Data[0].URL,
		Model: model,
		Size:  size,
	}, nil
}

func (p *VolcengineProvider) handleErrorResponse(resp *http.Response) error {
	body, _ := io.ReadAll(resp.Body)

	var errResp struct {
		Error struct {
			Code    string `json:"code"`
			Message string `json:"message"`
			Param   string `json:"param"`
			Type    string `json:"type"`
		} `json:"error"`
	}
	_ = json.Unmarshal(body, &errResp)

	message := errResp.Error.Message
	if message == "" {
		message = string(body)
	}

	modelsHint := ProviderSupportedModelsHint("volcengine")

	if errResp.Error.Code == "ModelNotOpen" {
		hint := "请前往火山引擎豆包大模型控制台（https://www.volcengine.com/product/doubao），点击控制台 -> 开通管理，勾选 Seedream 模型后再重试，或切换为已开通模型"
		if modelsHint != "" {
			hint += "。" + modelsHint
		}
		return &GenerateError{
			Provider: p.Name(),
			Code:     "model_not_open",
			Message:  "当前账户尚未开通所选模型",
			Hint:     hint,
			Original: fmt.Errorf("status %d: %s", resp.StatusCode, string(body)),
		}
	}

	switch resp.StatusCode {
	case http.StatusUnauthorized:
		return &GenerateError{
			Provider: p.Name(),
			Code:     "unauthorized",
			Message:  "Volcengine API Key 无效或已过期",
			Hint:     "请检查配置文件中的 api.image_key 是否正确，或前往火山引擎 Ark 控制台获取新的 API Key",
			Original: fmt.Errorf("status 401: %s", string(body)),
		}
	case http.StatusTooManyRequests:
		return &GenerateError{
			Provider: p.Name(),
			Code:     "rate_limit",
			Message:  "请求过于频繁，请稍后重试",
			Hint:     "Volcengine Ark API 有速率限制，请等待一段时间后再试",
			Original: fmt.Errorf("status 429: %s", string(body)),
		}
	case http.StatusBadRequest:
		hint := "请检查模型名称、尺寸等级和输出参数是否正确"
		if modelsHint != "" {
			hint += "。" + modelsHint
		}
		return &GenerateError{
			Provider: p.Name(),
			Code:     "bad_request",
			Message:  fmt.Sprintf("请求参数错误: %s", message),
			Hint:     hint,
			Original: fmt.Errorf("status 400: %s", string(body)),
		}
	case http.StatusNotFound:
		hint := "请检查 API 地址、模型名称或开通状态"
		if modelsHint != "" {
			hint += "。" + modelsHint
		}
		return &GenerateError{
			Provider: p.Name(),
			Code:     "not_found",
			Message:  fmt.Sprintf("资源不存在: %s", message),
			Hint:     hint,
			Original: fmt.Errorf("status 404: %s", string(body)),
		}
	case http.StatusPaymentRequired, http.StatusForbidden:
		return &GenerateError{
			Provider: p.Name(),
			Code:     "payment_required",
			Message:  "Volcengine 账户访问受限或未开通相关能力",
			Hint:     "请前往火山引擎 Ark 控制台检查账号状态、模型权限和计费配置",
			Original: fmt.Errorf("status %d: %s", resp.StatusCode, string(body)),
		}
	default:
		return &GenerateError{
			Provider: p.Name(),
			Code:     "unknown",
			Message:  fmt.Sprintf("Volcengine Ark API 返回错误 (HTTP %d)", resp.StatusCode),
			Hint:     "请稍后重试，或前往火山引擎 Ark 控制台查看服务状态",
			Original: fmt.Errorf("status %d: %s", resp.StatusCode, string(body)),
		}
	}
}
