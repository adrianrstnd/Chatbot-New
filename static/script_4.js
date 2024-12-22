document.getElementById("send-prompt").addEventListener("click", async () => {
  const promptInput = document.getElementById("user-prompt");
  const prompt = promptInput.value.trim();

  if (!prompt) return;

  const chatLog = document.getElementById("chat-log");
  chatLog.innerHTML += `<div><strong>You:</strong> ${prompt}</div>`;

  try {
      const response = await fetch("/process-message", {
          method: "POST",
          headers: {
              "Content-Type": "application/json",
          },
          body: JSON.stringify({ userMessage: prompt }),
      });

      const result = await response.json();
      chatLog.innerHTML += `<div><strong>Bot:</strong> ${result.botResponse}</div>`;
      chatLog.scrollTop = chatLog.scrollHeight;
  } catch (error) {
      console.error("Error processing message:", error);
  }

  promptInput.value = "";
});
