document.getElementById("upload-form").addEventListener("submit", async (e) => {
  e.preventDefault();

  const fileInput = document.getElementById("file-upload");
  const uploadBtn = document.getElementById("upload-btn");
  const spinner = document.getElementById("upload-spinner");
  const uploadStatus = document.getElementById("upload-status");

  const formData = new FormData();
  formData.append("file", fileInput.files[0]);

  // Tampilkan spinner dan nonaktifkan tombol
  spinner.classList.remove("hidden");
  uploadBtn.disabled = true;
  uploadStatus.innerText = "";

  try {
    const response = await fetch("/process-document", {
      method: "POST",
      body: formData,
    });
    const result = await response.json();
    uploadStatus.innerText = result.botResponse;

    // Perbarui daftar dokumen setelah upload berhasil
    fetchDocumentList();
  } catch (error) {
    console.error("Error uploading document:", error);
    uploadStatus.innerText = "An error occurred during upload.";
  } finally {
    // Sembunyikan spinner dan aktifkan tombol
    spinner.classList.add("hidden");
    uploadBtn.disabled = false;
    // Kosongkan form setelah selesai
    document.getElementById("upload-form").reset();
  }
});

document.getElementById("delete-form").addEventListener("submit", async (e) => {
  e.preventDefault();

  const fileNameInput = document.getElementById("file-delete");
  const documentName = fileNameInput.value.trim();

  if (!documentName) {
    document.getElementById("delete-status").innerText =
      "Please enter a document name to delete.";
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
    document.getElementById("delete-status").innerText =
      result.botResponse || result.error;

    // Perbarui daftar dokumen setelah delete berhasil
    fetchDocumentList();
  } catch (error) {
    console.error("Error deleting document:", error);
    document.getElementById("delete-status").innerText =
      "An error occurred while deleting the document.";
  } finally {
    // Kosongkan form setelah selesai
    document.getElementById("delete-form").reset();
  }
});

// Fungsi untuk mengambil daftar dokumen dan menampilkannya
async function fetchDocumentList() {
  const documentList = document.getElementById("document-list");
  documentList.innerHTML = "<li>Loading...</li>";

  try {
    const response = await fetch("/list-documents");
    const result = await response.json();

    if (result.documents && result.documents.length > 0) {
      documentList.innerHTML = ""; // Kosongkan daftar sebelumnya
      result.documents.forEach((doc) => {
        const listItem = document.createElement("li");
        listItem.innerText = doc;
        documentList.appendChild(listItem);
      });
    } else {
      documentList.innerHTML = "<li>No documents found.</li>";
    }
  } catch (error) {
    console.error("Error fetching document list:", error);
    documentList.innerHTML = "<li>Failed to load documents.</li>";
  }
}

// Panggil fungsi saat halaman dimuat
document.addEventListener("DOMContentLoaded", fetchDocumentList);
