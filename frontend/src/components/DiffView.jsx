export default function DiffView({ diff }) {
  if (!diff) return <p className="content-text">변경 사항이 없습니다.</p>;

  const lines = diff.split("\n");

  return (
    <div className="diff-view">
      <div className="code-block-header">
        <span className="code-block-label">diff</span>
      </div>
      <pre className="diff-content">
        {lines.map((line, i) => {
          let cls = "diff-line";
          if (line.startsWith("+++") || line.startsWith("---")) cls += " diff-meta";
          else if (line.startsWith("@@")) cls += " diff-hunk";
          else if (line.startsWith("+")) cls += " diff-add";
          else if (line.startsWith("-")) cls += " diff-del";

          return (
            <div key={i} className={cls}>
              {line}
            </div>
          );
        })}
      </pre>
    </div>
  );
}
