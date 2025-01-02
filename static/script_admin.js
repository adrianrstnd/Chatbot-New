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

document.getElementById("delete-form").addEventListener("submit", async (e) => {
    e.preventDefault();
  
    const fileNameInput = document.getElementById("file-delete");
    const documentName = fileNameInput.value.trim();
  
    if (!documentName) {
      document.getElementById("delete-status").innerText = "Please enter a document name to delete.";
      return;
    }
  
    try {
      const response = await fetch("/delete-document", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ documentName }),
      });
  
      const result = await response.json();
      document.getElementById("delete-status").innerText = result.botResponse || result.error;
    } catch (error) {
      console.error("Error deleting document:", error);
      document.getElementById("delete-status").innerText = "An error occurred while deleting the document.";
    }
  });

