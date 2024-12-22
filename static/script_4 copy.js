document.getElementById("upload-form").addEventListener("submit", async (e) => {
  e.preventDefault();

  const fileInput = document.getElementById("file-upload");
  const formData = new FormData();
  formData.append("file", fileInput.files[0]);

  try {
      const response = await fetch("/process-document", {
          method: "POST",
          body: formData,
      });
      const result = await response.json();
      document.getElementById("upload-status").innerText = result.botResponse;
  } catch (error) {
      console.error("Error uploading document:", error);
  }
});