package ampapi

import (
	"crypto/tls"
	"io"
	"net/http"
	"regexp"
	"strings"
	"time"

	"main/utils/httputil"
)

// DEFAULT_DEVELOPER_TOKEN is the official Apple Music Web Player authorization token.
// Embedded as a fail-safe fallback when CDN dynamic extraction is blocked by network or GFW.
const DEFAULT_DEVELOPER_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJFUzI1NiIsImtpZCI6IldlYlBsYXlLaWQifQ.eyJpc3MiOiJBTVBXZWJQbGF5IiwiaWF0IjoxNzg2NjMyOTI0LCJleHAiOjE3OTI2ODA5MjQsInJvb3RfaHR0cHNfb3JpZ2luIjpbImFwcGxlLmNvbSJdfQ.hBgj61sZf-y7bmuvT-joXAUAcf7TVJ51732xnH5vFkLHOmsQHxVqGMYUuI4h8c0-RX3fRY3moylhLW8fewFJyw"

var (
	jsRegex  = regexp.MustCompile(`/(?:assets|web-player)/[^"'\s<>]+\.js`)
	jwtRegex = regexp.MustCompile(`eyJ[A-Za-z0-9-_=]{20,}\.[A-Za-z0-9-_=]{20,}\.[A-Za-z0-9-_=]{20,}`)
)

const userAgent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"

func GetToken() (string, error) {
	client := httputil.Client
	if client == nil {
		client = &http.Client{
			Timeout: 10 * time.Second,
			Transport: &http.Transport{
				TLSClientConfig: &tls.Config{InsecureSkipVerify: true},
			},
		}
	}

	req, err := http.NewRequest("GET", "https://music.apple.com", nil)
	if err != nil {
		return DEFAULT_DEVELOPER_TOKEN, nil
	}
	req.Header.Set("User-Agent", userAgent)
	req.Header.Set("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8")
	req.Header.Set("Accept-Language", "en-US,en;q=0.9")

	resp, err := client.Do(req)
	if err != nil {
		// Network issue or CDN block -> use embedded fallback token
		return DEFAULT_DEVELOPER_TOKEN, nil
	}
	defer resp.Body.Close()

	bodyBytes, err := io.ReadAll(resp.Body)
	if err != nil {
		return DEFAULT_DEVELOPER_TOKEN, nil
	}
	html := string(bodyBytes)

	// 1. Check if token exists directly in HTML
	if token := jwtRegex.FindString(html); token != "" {
		return token, nil
	}

	// 2. Scan JS bundles
	allMatches := jsRegex.FindAllString(html, -1)
	if len(allMatches) == 0 {
		return DEFAULT_DEVELOPER_TOKEN, nil
	}

	var prioritized []string
	var others []string
	for _, m := range allMatches {
		lower := strings.ToLower(m)
		if strings.Contains(lower, "index") || strings.Contains(lower, "main") || strings.Contains(lower, "player") {
			prioritized = append(prioritized, m)
		} else {
			others = append(others, m)
		}
	}
	candidates := append(prioritized, others...)

	for _, jsUri := range candidates {
		fullUrl := jsUri
		if !strings.HasPrefix(fullUrl, "http") {
			fullUrl = "https://music.apple.com" + jsUri
		}

		jsReq, err := http.NewRequest("GET", fullUrl, nil)
		if err != nil {
			continue
		}
		jsReq.Header.Set("User-Agent", userAgent)

		jsResp, err := client.Do(jsReq)
		if err != nil {
			continue
		}

		jsBytes, err := io.ReadAll(jsResp.Body)
		jsResp.Body.Close()
		if err != nil {
			continue
		}

		jsContent := string(jsBytes)
		if token := jwtRegex.FindString(jsContent); token != "" {
			return token, nil
		}
	}

	// Fallback to embedded token
	return DEFAULT_DEVELOPER_TOKEN, nil
}


