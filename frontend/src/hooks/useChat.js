import { useState, useCallback } from "react";
import { sendMessage } from "../services/api";

export default function useChat() {
  const [messages, setMessages] = useState([]);
  const [isLoading, setIsLoading] = useState(false);

  const send = useCallback(async (text) => {
    const userMsg = {
      role: "user",
      contents: [{ type: "text", body: text }],
      timestamp: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setIsLoading(true);

    try {
      const response = await sendMessage(text);
      setMessages((prev) => [...prev, response]);
    } catch (err) {
      const errorMsg = {
        role: "assistant",
        contents: [{ type: "text", body: `오류가 발생했습니다: ${err.message}` }],
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const clear = useCallback(() => setMessages([]), []);

  return { messages, isLoading, send, clear };
}
