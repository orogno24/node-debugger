import CodeBlock from "./CodeBlock";

export default function YamlView({ code }) {
  return <CodeBlock code={code} language="yaml" label="YAML" />;
}
