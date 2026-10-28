// Apply the saved choice before the stylesheet paints, including on slow connections.
(() => {
  let theme = "dark";
  try {
    if (localStorage.getItem("forest.theme") === "light") theme = "light";
  } catch { /* Storage is optional; dark remains the default. */ }
  document.documentElement.dataset.theme = theme;
})();
