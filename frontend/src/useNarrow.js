import { useEffect, useState } from "react";

// 좁은 화면(모바일) 여부. placeholder처럼 CSS로 분기할 수 없는 값에 쓴다.
// Tailwind의 md 브레이크포인트(768px)와 맞춘다.
export default function useNarrow(maxWidth = 767) {
  const query = `(max-width: ${maxWidth}px)`;
  const [narrow, setNarrow] = useState(
    () => typeof window !== "undefined" && window.matchMedia(query).matches
  );

  useEffect(() => {
    const mq = window.matchMedia(query);
    const onChange = (e) => setNarrow(e.matches);
    setNarrow(mq.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, [query]);

  return narrow;
}
