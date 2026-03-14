import { useRef, useEffect } from "react";
import useChat from "../hooks/useChat";
import ChatInput from "./ChatInput";
import MessageBubble from "./MessageBubble";

export default function ChatWindow() {
  const { messages, isLoading, send } = useChat();
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  return (
    <div className="chat-window">
      <div className="chat-messages">
        {messages.length === 0 && (
          <div className="chat-welcome">
            <h2>K8s ChatOps Console</h2>
            <p>무엇을 도와드릴까요?</p>
            <ul>
              <li><code>backend-api pod 상태 확인해줘</code></li>
              <li><code>frontend values 보여줘</code></li>
              <li><code>replicas를 3으로 바꿔줘</code></li>
              <li><code>diff 보여줘</code></li>
              <li><code>저장해줘</code></li>
            </ul>
          </div>
        )}
        {messages.map((msg, i) => (
          <MessageBubble key={i} message={msg} />
        ))}
        {isLoading && (
          <div className="message assistant">
            <div className="message-body">
              <span className="loading-dots">분석 중</span>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>
      <ChatInput onSend={send} disabled={isLoading} />
    </div>
  );
}
