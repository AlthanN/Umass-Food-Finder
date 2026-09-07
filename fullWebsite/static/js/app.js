const form = document.querySelector("#search-form");
const input = document.querySelector("#food-name");
const searchButton = document.querySelector("#search-button");
const suggestions = document.querySelector("#suggestions");
const resultsSection = document.querySelector("#results");
const statusBox = document.querySelector("#status");
const feedbackForm = document.querySelector("#feedback-form");
const feedbackButton = document.querySelector("#feedback-button");
const feedbackStatus = document.querySelector("#feedback-status");

let suggestionTimer;
let suggestionController;

form.addEventListener("submit", (event) => {
  event.preventDefault();
  closeSuggestions();
  search(input.value);
});

input.addEventListener("input", () => {
  window.clearTimeout(suggestionTimer);
  suggestionController?.abort();
  const query = input.value.trim();
  if (query.length < 2) {
    closeSuggestions();
    return;
  }
  suggestionTimer = window.setTimeout(() => loadSuggestions(query), 250);
});

document.addEventListener("click", (event) => {
  if (!form.contains(event.target)) closeSuggestions();
});

feedbackForm?.addEventListener("submit", submitFeedback);

async function submitFeedback(event) {
  event.preventDefault();
  if (!feedbackForm.checkValidity()) {
    feedbackForm.reportValidity();
    return;
  }

  setFeedbackLoading(true);
  showFeedbackStatus("Sending your feedback…");
  try {
    const response = await fetch(feedbackForm.dataset.endpoint, {
      method: "POST",
      body: new FormData(feedbackForm),
      headers: { Accept: "application/json" },
    });

    if (response.ok) {
      feedbackForm.reset();
      showFeedbackStatus("Thank you! Your feedback was sent.", "success");
    } else if (response.status === 429) {
      showFeedbackStatus("Too many submissions were sent recently. Please try again later.", "error");
    } else {
      showFeedbackStatus("Your feedback could not be sent. Please check the form and try again.", "error");
    }
  } catch (error) {
    showFeedbackStatus("Your feedback could not be sent. Check your connection and try again.", "error");
  } finally {
    setFeedbackLoading(false);
  }
}

function showFeedbackStatus(message, kind = "info") {
  feedbackStatus.textContent = message;
  feedbackStatus.dataset.kind = kind;
}

function setFeedbackLoading(isLoading) {
  feedbackButton.disabled = isLoading;
  feedbackButton.textContent = isLoading ? "Sending…" : "Send feedback";
}

async function search(rawQuery) {
  const query = rawQuery.trim();
  if (!query) {
    showStatus("Please enter a food name.", "warning");
    input.focus();
    return;
  }

  setLoading(true);
  showStatus("Searching the loaded menus…");
  clearResults();
  try {
    const { response, data } = await requestSearch(query);
    renderResponse(data, response.ok);
  } catch (error) {
    showStatus("The search could not be completed. Please try again.", "error");
  } finally {
    setLoading(false);
  }
}

async function loadSuggestions(query) {
  suggestionController = new AbortController();
  try {
    const { response, data } = await requestSearch(query, suggestionController.signal);
    if (!response.ok || !data.results?.length) {
      closeSuggestions();
      return;
    }

    const names = [...new Set(data.results.map((item) => item.food))].slice(0, 7);
    suggestions.replaceChildren(...names.map(createSuggestion));
    suggestions.hidden = names.length === 0;
    input.setAttribute("aria-expanded", String(names.length > 0));
  } catch (error) {
    if (error.name !== "AbortError") closeSuggestions();
  }
}

async function requestSearch(query, signal) {
  const response = await fetch(`/search?foodName=${encodeURIComponent(query)}`, { signal });
  return { response, data: await response.json() };
}

function createSuggestion(name) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "suggestion";
  button.setAttribute("role", "option");
  button.textContent = name;
  button.addEventListener("click", () => {
    input.value = name;
    closeSuggestions();
    search(name);
  });
  return button;
}

function renderResponse(data, requestSucceeded) {
  if (!requestSucceeded || data.data_status === "unavailable") {
    showStatus(data.message || "Menu data is unavailable.", "error");
    return;
  }

  if (!data.results.length) {
    showStatus(data.message || "No matching menu items were found.", data.data_status === "partial" ? "warning" : "info");
    return;
  }

  const grouped = Object.groupBy
    ? Object.groupBy(data.results, (item) => item.location)
    : data.results.reduce((groups, item) => {
        (groups[item.location] ||= []).push(item);
        return groups;
      }, {});

  document.querySelectorAll(".location").forEach((card) => {
    const target = card.querySelector(".location-results");
    const items = grouped[card.dataset.location] || [];
    target.replaceChildren(...(items.length ? items.map(createFoodItem) : [createEmptyMessage()]));
  });
  resultsSection.hidden = false;
  const kind = data.data_status === "partial" ? "warning" : "info";
  showStatus(data.message || `${data.results.length} menu ${data.results.length === 1 ? "item" : "items"} found.`, kind);
}

function createFoodItem(item) {
  const wrapper = document.createElement("div");
  wrapper.className = "food-item";
  const name = document.createElement("p");
  name.className = "food-name";
  name.textContent = item.food;
  const details = document.createElement("p");
  details.className = "food-details";
  details.textContent = `${item.meal} · ${item.category} · ${formatDate(item.date)}`;
  wrapper.append(name, details);
  return wrapper;
}

function createEmptyMessage() {
  const message = document.createElement("p");
  message.className = "location-empty";
  message.textContent = "No matching items at this dining hall.";
  return message;
}

function formatDate(date) {
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeZone: "UTC" }).format(new Date(`${date}T00:00:00Z`));
}

function clearResults() {
  resultsSection.hidden = true;
  document.querySelectorAll(".location-results").forEach((node) => node.replaceChildren());
}

function closeSuggestions() {
  suggestions.hidden = true;
  suggestions.replaceChildren();
  input.setAttribute("aria-expanded", "false");
}

function showStatus(message, kind = "info") {
  statusBox.textContent = message;
  statusBox.dataset.kind = kind;
}

function setLoading(isLoading) {
  searchButton.disabled = isLoading;
  searchButton.textContent = isLoading ? "Searching…" : "Search menus";
}
