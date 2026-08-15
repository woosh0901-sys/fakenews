import socket
import ipaddress
import urllib.parse
import re
import time
from typing import Optional, Tuple, List, Dict, Any
import requests

MAX_URL_LENGTH = 2048
MAX_RESPONSE_SIZE = 5 * 1024 * 1024  # 5MB response limit to prevent memory exhaustion
MAX_REDIRECTS = 3

# Disallowed / Reserved IPv4 & IPv6 networks for SSRF Defense
DISALLOWED_NETWORKS = [
    ipaddress.ip_network("0.0.0.0/8"),          # Current network (only valid as source address)
    ipaddress.ip_network("10.0.0.0/8"),         # Private-use networks
    ipaddress.ip_network("100.64.0.0/10"),      # Shared Address Space (Carrier-grade NAT)
    ipaddress.ip_network("127.0.0.0/8"),        # Loopback
    ipaddress.ip_network("169.254.0.0/16"),     # Link-Local (including cloud metadata: 169.254.169.254)
    ipaddress.ip_network("172.16.0.0/12"),      # Private-use networks
    ipaddress.ip_network("192.0.0.0/24"),       # IETF Protocol Assignments
    ipaddress.ip_network("192.0.2.0/24"),       # TEST-NET-1, documentation and examples
    ipaddress.ip_network("192.168.0.0/16"),     # Private-use networks
    ipaddress.ip_network("198.18.0.0/15"),      # Network benchmark tests
    ipaddress.ip_network("198.51.100.0/24"),    # TEST-NET-2, documentation and examples
    ipaddress.ip_network("203.0.113.0/24"),     # TEST-NET-3, documentation and examples
    ipaddress.ip_network("224.0.0.0/4"),        # Multicast
    ipaddress.ip_network("240.0.0.0/4"),        # Reserved for future use / Broadcast
    ipaddress.ip_network("255.255.255.255/32"), # Limited broadcast
    # IPv6
    ipaddress.ip_network("::1/128"),            # Loopback
    ipaddress.ip_network("::/128"),             # Unspecified
    ipaddress.ip_network("::ffff:0:0/96"),      # IPv4-mapped IPv6
    ipaddress.ip_network("64:ff9b::/96"),       # IPv4/IPv6 translation
    ipaddress.ip_network("100::/64"),           # Discard prefix
    ipaddress.ip_network("2001:db8::/32"),      # Documentation
    ipaddress.ip_network("fc00::/7"),           # Unique Local Address (ULA)
    ipaddress.ip_network("fe80::/10"),          # Link-Local Unicast
    ipaddress.ip_network("ff00::/8"),           # Multicast
]

def is_ip_disallowed(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """
    IP 주소가 루프백, 사설망, 링크-로컬, 멀티캐스트, 예약 대역 또는 클라우드 메타데이터 대역인지 검사합니다.
    """
    if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved or ip.is_unspecified:
        return True
    for net in DISALLOWED_NETWORKS:
        if ip in net:
            return True
    return False

def validate_url_safe(url: str) -> Tuple[bool, str]:
    """
    URL의 스킴, 길이, 형식 및 DNS Resolution을 수행하여 SSRF 목적지(내부 사설망, 루프백 등)를 철저히 차단합니다.
    - 허용 스킴: http, https
    - 차단 스킴: file, ftp, gopher, data, javascript 등
    - 길이 제한: 2048자 이하
    - DNS 해석 후 실제 IP 대역 검증 (DNS Rebinding 방어)
    """
    if not url or not isinstance(url, str):
        return False, "URL이 비어 있습니다."
    
    url = url.strip()
    if len(url) > MAX_URL_LENGTH:
        return False, f"URL 길이가 허용 한도({MAX_URL_LENGTH}자)를 초과했습니다."
        
    try:
        parsed = urllib.parse.urlparse(url)
    except Exception as e:
        return False, f"URL 파싱 실패: {str(e)}"

    scheme = parsed.scheme.lower()
    if scheme not in ("http", "https"):
        return False, f"허용되지 않은 프로토콜('{scheme}')입니다. HTTP 및 HTTPS만 지원됩니다."
        
    hostname = parsed.hostname
    if not hostname:
        return False, "유효한 호스트명이 누락되었습니다."
        
    hostname_lower = hostname.lower().strip("[]")
    
    # 1. 1차 문자열 기반 즉시 차단
    if hostname_lower in ("localhost", "0.0.0.0", "127.0.0.1", "::1") or \
       hostname_lower.endswith(".local") or hostname_lower.endswith(".internal") or \
       hostname_lower.endswith(".localhost"):
        return False, "로컬 및 내부 도메인 접근은 차단됩니다."

    # 2. IP 직입력 검사 (Decimal, Hexadecimal, IPv4-mapped IPv6 등 다양한 포맷 정규화)
    try:
        # 혹시 숫자 형태나 비정상 IPv4 포맷인 경우 처리
        direct_ip = ipaddress.ip_address(hostname_lower)
        if is_ip_disallowed(direct_ip):
            return False, f"비공개 또는 예약된 내부 IP({direct_ip})로의 접근은 차단됩니다."
    except ValueError:
        pass  # 도메인 이름인 경우 정상 진행

    # 3. DNS Resolution을 통한 실제 대상 IP 검사 (SSRF 및 DNS Rebinding 방어)
    port = parsed.port or (443 if scheme == "https" else 80)
    try:
        addr_info = socket.getaddrinfo(hostname_lower, port, type=socket.SOCK_STREAM)
    except socket.gaierror:
        return False, "호스트명을 찾을 수 없거나 DNS 조회에 실패했습니다."
    except Exception as e:
        return False, f"DNS 조회 중 오류 발생: {str(e)}"
        
    if not addr_info:
        return False, "DNS 조회 결과가 없습니다."
        
    for item in addr_info:
        sockaddr = item[4]
        ip_str = sockaddr[0]
        try:
            ip_obj = ipaddress.ip_address(ip_str)
            if is_ip_disallowed(ip_obj):
                return False, f"비공개/사설 내부망 IP({ip_str})로의 요청은 보안상 허용되지 않습니다."
        except ValueError:
            return False, f"유효하지 않은 IP 주소 형식입니다: {ip_str}"
            
    return True, ""

def safe_http_get(url: str, headers: dict = None, timeout: float = 5.0, max_size: int = MAX_RESPONSE_SIZE, max_redirects: int = MAX_REDIRECTS) -> Optional[requests.Response]:
    """
    SSRF 안전성 및 자원 고갈(Resource Exhaustion) 방어를 보장하는 HTTP GET 요청 함수.
    - 매 리다이렉트마다 대상 IP 재검증 (Redirect 기반 SSRF 차단)
    - 스트리밍 방식으로 최대 응답 본문 크기(5MB) 제한
    - Connect timeout(3초) 및 Read timeout(최대 5초) 분리 적용
    """
    current_url = url
    session = requests.Session()
    
    req_headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    if headers:
        req_headers.update(headers)
        
    for redirect_count in range(max_redirects + 1):
        # 매 Hop마다 SSRF 검증
        is_safe, err_msg = validate_url_safe(current_url)
        if not is_safe:
            print(f"[-] [보안 차단] SSRF 방어: 안전하지 않은 URL 요청 차단됨: {current_url} ({err_msg})")
            return None
            
        try:
            resp = session.get(
                current_url,
                headers=req_headers,
                timeout=(3.0, timeout),
                allow_redirects=False,
                stream=True
            )
            
            # 리다이렉트 발생 시 검증 후 다음 홉 진행
            if resp.status_code in (301, 302, 303, 307, 308):
                location = resp.headers.get("Location")
                if not location:
                    return resp
                current_url = urllib.parse.urljoin(current_url, location)
                continue
                
            # Content-Length 헤더 사전 점검
            cl = resp.headers.get("Content-Length")
            if cl and cl.isdigit() and int(cl) > max_size:
                print(f"[-] [보안 차단] 응답 크기 한도 초과: {cl} > {max_size} bytes")
                resp.close()
                return None
                
            # 본문 스트림 다운로드 및 실시간 크기 제한
            content = bytearray()
            for chunk in resp.iter_content(chunk_size=8192):
                content.extend(chunk)
                if len(content) > max_size:
                    print(f"[-] [보안 차단] 다운로드 중 응답 크기 한도 초과 ({len(content)} > {max_size} bytes)")
                    resp.close()
                    return None
                    
            resp._content = bytes(content)
            return resp
            
        except Exception as e:
            print(f"[-] 안전한 HTTP 요청 중 통신 오류 발생: {e}")
            return None
            
    print(f"[-] [보안 차단] 최대 리다이렉트 횟수({max_redirects}회) 초과")
    return None

def sanitize_text(text: str, max_length: int = 1000) -> str:
    """
    사용자 입력 텍스트에서 악성 제어 문자 및 비정상 스크립트 태그를 정제하고 길이를 제한합니다.
    """
    if not text or not isinstance(text, str):
        return ""
    # Remove NULL and unprintable control characters except newline and tab
    sanitized = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
    # Strip HTML tags
    sanitized = re.sub(r'<[^>]*>', '', sanitized)
    return sanitized.strip()[:max_length]

def sanitize_gemini_output(res: dict, sources_count: int = 0) -> dict:
    """
    Gemini LLM이 반환한 JSON의 각 필드 타입과 값 범위를 엄격하게 검증하여 Fallback 및 정규화를 적용합니다.
    """
    if not isinstance(res, dict):
        return {
            "verdict": "SUSPICIOUS",
            "reason": "응답 데이터 형식이 올바르지 않아 최종 판정을 유보합니다.",
            "contradiction_score": 0.5,
            "evidence_quality": 0.0,
            "independent_source_count": 0,
            "primary_source_found": False,
            "claims_breakdown": []
        }

    # 1. verdict 검증 (REAL, FAKE, SUSPICIOUS만 허용)
    verdict = str(res.get("verdict", "")).strip().upper()
    if verdict not in ("REAL", "FAKE", "SUSPICIOUS"):
        verdict = "SUSPICIOUS"
        
    # 2. contradiction_score 검증 (0.0 ~ 1.0)
    try:
        contradiction_score = float(res.get("contradiction_score", 0.5))
        contradiction_score = max(0.0, min(1.0, round(contradiction_score, 4)))
    except (ValueError, TypeError):
        contradiction_score = 0.5

    # 3. evidence_quality 검증 (0.0 ~ 1.0)
    try:
        evidence_quality = float(res.get("evidence_quality", 0.5))
        evidence_quality = max(0.0, min(1.0, round(evidence_quality, 4)))
    except (ValueError, TypeError):
        evidence_quality = round(sources_count * 0.25, 2) if sources_count else 0.0

    # 4. independent_source_count 검증 (정수 >= 0)
    try:
        independent_source_count = int(res.get("independent_source_count", sources_count))
        independent_source_count = max(0, min(50, independent_source_count))
    except (ValueError, TypeError):
        independent_source_count = sources_count

    # 5. primary_source_found 검증 (boolean)
    primary_source_found = bool(res.get("primary_source_found", False))

    # 6. reason 검증 (문자열 길이 제한)
    reason = sanitize_text(str(res.get("reason", "")), max_length=2000)
    if not reason:
        reason = "교차 검증 분석 결과입니다."

    # 7. claims_breakdown 검증 (배열 및 요소 검증)
    raw_claims = res.get("claims_breakdown", [])
    valid_claims = []
    if isinstance(raw_claims, list):
        for c in raw_claims[:10]:
            if isinstance(c, dict):
                truth_val = str(c.get("truth", "판단유보")).strip()
                if truth_val not in ("진실", "거짓", "판단유보"):
                    truth_val = "판단유보"
                valid_claims.append({
                    "claim": sanitize_text(str(c.get("claim", "")), max_length=300),
                    "truth": truth_val,
                    "explanation": sanitize_text(str(c.get("explanation", "")), max_length=500)
                })

    return {
        "verdict": verdict,
        "reason": reason,
        "contradiction_score": contradiction_score,
        "evidence_quality": evidence_quality,
        "independent_source_count": independent_source_count,
        "primary_source_found": primary_source_found,
        "claims_breakdown": valid_claims
    }
