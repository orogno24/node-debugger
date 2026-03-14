import CodeBlock from "./CodeBlock";
import DiffView from "./DiffView";
import YamlView from "./YamlView";

const CONTENT_RENDERERS = {
  text: ({ body }) => <p className="content-text">{body}</p>,
  code: ({ body, language }) => <CodeBlock code={body} language={language} />,
  yaml: ({ body }) => <YamlView code={body} />,
  diff: ({ body }) => <DiffView diff={body} />,
  command: ({ body }) => <CodeBlock code={body} language="bash" label="실행 명령어" />,
};

export default function MessageBubble({ message }) {
  const { role, contents = [] } = message;

  return (
    <div className={`message ${role}`}>
      <div className="message-body">
        {contents.map((block, i) => {
          const Renderer = CONTENT_RENDERERS[block.type] || CONTENT_RENDERERS.text;
          return <div key={i} className="content-block">{Renderer(block)}</div>;
        })}
      </div>
    </div>
  );
}
