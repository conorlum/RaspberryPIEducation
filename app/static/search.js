(function () {
  var form = document.getElementById("search-form");
  var input = document.getElementById("search-input");
  var prompt = document.getElementById("search-prompt");
  var status = document.getElementById("search-status");
  var resultsPanel = document.getElementById("search-results");
  if (!form || !input || !prompt || !status || !resultsPanel) return;

  var requestId = 0;

  function showPrompt() {
    prompt.hidden = false;
    status.hidden = true;
    resultsPanel.hidden = true;
    resultsPanel.innerHTML = "";
  }

  function showLoading() {
    prompt.hidden = true;
    status.hidden = false;
    resultsPanel.hidden = true;
  }

  form.addEventListener("submit", function (event) {
    event.preventDefault();

    var term = input.value.trim();
    if (!term) {
      requestId += 1; // invalidate any in-flight search
      showPrompt();
      return;
    }

    runSearch(term);
  });

  function runSearch(term) {
    var thisRequest = ++requestId;
    showLoading();
    fetch("/api/search-suggest?q=" + encodeURIComponent(term))
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (thisRequest !== requestId) return; // a newer search already superseded this
        renderResults(data.results || []);
      })
      .catch(function () {
        if (thisRequest !== requestId) return;
        renderResults([]);
      });
  }

  function renderResults(results) {
    prompt.hidden = true;
    status.hidden = true;
    resultsPanel.hidden = false;
    resultsPanel.innerHTML = "";

    if (!results.length) {
      var empty = document.createElement("p");
      empty.className = "library-empty-filtered";
      empty.textContent = "No se encontraron artículos.";
      resultsPanel.appendChild(empty);
      return;
    }

    var list = document.createElement("ul");
    list.className = "search-results-list";
    results.forEach(function (item) {
      var li = document.createElement("li");
      var a = document.createElement("a");
      a.href = item.url;

      var title = document.createElement("span");
      title.className = "search-result-title";
      title.textContent = item.title;

      var source = document.createElement("span");
      source.className = "search-result-source";
      source.textContent = item.book_title;

      a.appendChild(title);
      a.appendChild(source);
      li.appendChild(a);
      list.appendChild(li);
    });
    resultsPanel.appendChild(list);
  }
})();
