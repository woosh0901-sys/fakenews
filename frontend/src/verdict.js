// 판정/진실성 표기 톤.
// Tailwind JIT이 클래스를 정적으로 스캔하므로 반드시 완전한 리터럴 문자열이어야 한다.
// (`text-${x}-700` 같은 조합은 CSS가 생성되지 않는다)

export const VERDICT = {
  REAL: {
    label: "진짜 뉴스",
    short: "진짜",
    text: "text-success-700",
    rule: "border-success-500",
    bar: "bg-success-500",
  },
  FAKE: {
    label: "가짜 뉴스",
    short: "가짜",
    text: "text-error-700",
    rule: "border-error-500",
    bar: "bg-error-500",
  },
  SUSPICIOUS: {
    label: "의심 / 과장",
    short: "의심",
    text: "text-warning-700",
    rule: "border-warning-500",
    bar: "bg-warning-500",
  },
};

export const verdictTone = (verdict) => VERDICT[verdict] ?? VERDICT.SUSPICIOUS;

const TRUTH = {
  진실: "text-success-700",
  거짓: "text-error-700",
  판단유보: "text-warning-700",
};

export const truthTone = (truth) => TRUTH[truth] ?? "text-warning-700";
