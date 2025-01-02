document.getElementById("send-prompt").addEventListener("click", async () => {
  const promptInput = document.getElementById("user-prompt");
  const prompt = promptInput.value.trim();

  if (!prompt) return;

  const chatLog = document.getElementById("chat-log");
  const loading = document.getElementById("loading");
  chatLog.innerHTML += `<div class="user-message"> ${prompt}</div>`;

  // Menampilkan loading indicator
  loading.classList.add("visible");

  try {
    const response = await fetch("/process-message", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ userMessage: prompt }),
    });

    const result = await response.json();

    // Menyembunyikan loading indicator setelah mendapat respons
    loading.classList.remove("visible");

    // Menambahkan respons bot ke chat
    chatLog.innerHTML += `<div class="bot-response">${result.botResponse}</div>`;
    chatLog.scrollTop = chatLog.scrollHeight;
  } catch (error) {
    console.error("Error processing message:", error);
    loading.classList.remove("visible"); // Sembunyikan jika ada error
  }

  promptInput.value = "";
});
