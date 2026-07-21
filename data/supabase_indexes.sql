-- Supabase 쿼리 성능 최적화를 위한 인덱스 마이그레이션 SQL
-- 이 스크립트를 Supabase 대시보드 -> SQL Editor에 복사하여 실행하시면 인덱스가 생성됩니다.

-- 1. checks 테이블의 created_at 컬럼 인덱스 추가 (히스토리 정렬 최적화)
CREATE INDEX IF NOT EXISTS idx_checks_created_at ON checks (created_at DESC);

-- 2. check_references 테이블의 check_id 컬럼 인덱스 추가 (Foreign Key 조인 최적화)
CREATE INDEX IF NOT EXISTS idx_check_references_check_id ON check_references (check_id);

-- 3. checks 테이블의 verdict 컬럼 인덱스 추가 (통계 계산 최적화)
CREATE INDEX IF NOT EXISTS idx_checks_verdict ON checks (verdict);
