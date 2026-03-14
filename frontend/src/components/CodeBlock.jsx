import { Light as SyntaxHighlighter } from "react-syntax-highlighter";
import json from "react-syntax-highlighter/dist/esm/languages/hljs/json";
import yaml from "react-syntax-highlighter/dist/esm/languages/hljs/yaml";
import bash from "react-syntax-highlighter/dist/esm/languages/hljs/bash";
import accesslog from "react-syntax-highlighter/dist/esm/languages/hljs/accesslog";
import plaintext from "react-syntax-highlighter/dist/esm/languages/hljs/plaintext";
import { atomOneDark } from "react-syntax-highlighter/dist/esm/styles/hljs";

SyntaxHighlighter.registerLanguage("json", json);
SyntaxHighlighter.registerLanguage("yaml", yaml);
SyntaxHighlighter.registerLanguage("bash", bash);
SyntaxHighlighter.registerLanguage("accesslog", accesslog);
SyntaxHighlighter.registerLanguage("plaintext", plaintext);

const LANG_MAP = {
  log: "accesslog",
  path: "plaintext",
  text: "plaintext",
};

export default function CodeBlock({ code, language = "text", label }) {
  const handleCopy = () => {
    navigator.clipboard.writeText(code).catch(() => {});
  };

  const resolvedLang = LANG_MAP[language] || language;

  return (
    <div className="code-block">
      <div className="code-block-header">
        <span className="code-block-label">{label || language}</span>
        <button className="code-block-copy" onClick={handleCopy} title="복사">
          ⎘
        </button>
      </div>
      <SyntaxHighlighter
        language={resolvedLang}
        style={atomOneDark}
        customStyle={{ margin: 0, borderRadius: "0 0 6px 6px", fontSize: "13px" }}
        wrapLongLines
      >
        {code}
      </SyntaxHighlighter>
    </div>
  );
}
