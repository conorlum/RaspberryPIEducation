(function () {
  var input = document.getElementById("library-search");
  var browseGrid = document.getElementById("browse-grid");
  var resultsPanel = document.getElementById("search-results");
  if (!input || !browseGrid || !resultsPanel) return;

  var debounceTimer = null;
  var requestId = 0;

  input.addEventListener("input", function () {
    var term = input.value.trim();
    clearTimeout(debounceTimer);

    if (!term) {
      requestId += 1; // invalidate any in-flight search
      resultsPanel.hidden = true;
      resultsPanel.innerHTML = "";
      browseGrid.hidden = false;
      return;
    }

    debounceTimer = setTimeout(function () {
      runSearch(term);
    }, 250);
  });

  function runSearch(term) {
    var thisRequest = ++requestId;
    fetch("/api/search-suggest?q=" + encodeURIComponent(term))
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (thisRequest !== requestId) return; // a newer keystroke already superseded this
        renderResults(data.groups || []);
      })
      .catch(function () {
        if (thisRequest !== requestId) return;
        renderResults([]);
      });
  }

  function renderResults(groups) {
    browseGrid.hidden = true;
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
