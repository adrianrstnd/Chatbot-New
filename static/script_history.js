document.addEventListener("DOMContentLoaded", () => {
  const tableBody = document.querySelector("#historyTable tbody");
  const filterForm = document.querySelector("#filterForm");
  const pagination = document.querySelector("#pagination");
  let currentPage = 1;

  function fetchHistory(month = "", year = "", page = 1) {
    const url = `/history?month=${month}&year=${year}&page=${page}`;
    fetch(url)
      .then((response) => response.json())
      .then((data) => {
        // Clear table
        tableBody.innerHTML = "";

        if (data.history && data.history.length > 0) {
          // Map data to table rows
          const rows = data.history.map((entry, index) => {
            const { user_message, bot_response, timestamp } = entry;
            return `
              <tr>
                <td>${(page - 1) * 50 + index + 1}</td>
                <td>${user_message}</td>
                <td>${bot_response}</td>
                <td>${new Date(timestamp).toLocaleString()}</td>
              </tr>
            `;
          });

          tableBody.innerHTML = rows.join(""); // Render rows
          updatePaginationButtons(page, month, year, data.history.length < 50); // Update pagination
        } else {
          tableBody.innerHTML =
            '<tr><td colspan="4">No chat history available for the selected filters.</td></tr>';
          updatePaginationButtons(page, month, year, true); // Handle empty data
        }
      })
      .catch((err) => {
        console.error("Error fetching chat history:", err);
        tableBody.innerHTML =
          '<tr><td colspan="4">Failed to load data. Please try again later.</td></tr>';
      });
  }

  function updatePaginationButtons(page, month, year, isLastPage) {
    pagination.innerHTML = ""; // Clear pagination buttons

    // Previous button
    if (page > 1) {
      const prevButton = document.createElement("button");
      prevButton.textContent = "Previous";
      prevButton.addEventListener("click", () => {
        currentPage -= 1;
        fetchHistory(month, year, currentPage);
      });
      pagination.appendChild(prevButton);
    }

    // Current page indicator
    const pageIndicator = document.createElement("span");
    pageIndicator.textContent = `Page ${page}`;
    pagination.appendChild(pageIndicator);

    // Next button (only if not on the last page)
    if (!isLastPage) {
      const nextButton = document.createElement("button");
      nextButton.textContent = "Next";
      nextButton.addEventListener("click", () => {
        currentPage += 1;
        fetchHistory(month, year, currentPage);
      });
      pagination.appendChild(nextButton);
    }
  }

  filterForm.addEventListener("submit", (e) => {
    e.preventDefault();
    const month = document.querySelector("#month").value;
    const year = document.querySelector("#year").value;

    // Handle "All" selection for month
    const filterMonth = month === "All" ? "" : month;

    currentPage = 1; // Reset to the first page
    fetchHistory(filterMonth, year, currentPage);
  });

  // Initial fetch
  fetchHistory();
});
