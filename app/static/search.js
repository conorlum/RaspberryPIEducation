(function () {
  var form = document.getElementById("search-form");
  var input = document.getElementById("search-input");
  var prompt = document.getElementById("search-prompt");
  var status = document.getElementById("search-status");
  var resultsPanel = document.getElementById("search-results");
  if (!form || !input || !prompt || !status || !resultsPanel) return;

  var debounceTimer = null;
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

  input.addEventListener("input", function () {
    var term = input.value.trim();
    clearTimeout(debounceTimer);

    if (!term) {
      requestId += 1; // invalidate any in-flight search
      showPrompt();
      return;
    }

    debounceTimer = setTimeout(function () {
      runSearch(term);
    }, 250);
  });

  form.addEventListener("submit", function (event) {
    event.preventDefault();
    clearTimeout(debounceTimer);

    var term = input.value.trim();
    if (!term) {
      requestId += 1;
      showPrompt();
      return;
    }

    runSearch(term); // fires immediately, bypassing the debounce wait
  });

  function runSearch(term) {
    var thisRequest = ++requestId;
    showLoading();
    fetch("/api/search-suggest?q=" + encodeURIComponent(term))
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (thisRequest !== requestId) return; // a newer search already superseded this
        renderResults(data.groups || []);
      })
      .catch(function () {
        if (thisRequest !== requestId) return;
        renderResults([]);
      });
  }

  function renderResults(groups) {
    prompt.hidden = true;
    status.hidden = true;
    resultsPanel.hidden = false;
    resultsPanel.innerHTML = "";

    if (!groups.length) {
      var empty = document.createElement("p");
      empty.className = "library-empty-filtered";
      empty.textContent = "No matching articles.";
      resultsPanel.appendChild(empty);
      return;
    }

    groups.forEach(function (group) {
      var section = document.createElement("section");
      section.className = "search-group";

      var heading = document.createElement("h2");
      heading.textContent = group.book_title;
      section.appendChild(heading);

      var list = document.createElement("ul");
      group.articles.forEach(function (article) {
        var li = document.createElement("li");
        var a = document.createElement("a");
        a.href = article.url;
        a.textContent = article.title;
        li.appendChild(a);
        list.appendChild(li);
      });
      section.appendChild(list);
      resultsPanel.appendChild(section);
    });
  }
})();
