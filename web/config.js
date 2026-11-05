// Default settings for the web app. tools/build_web.py writes its own copy
// into the built site; this one lets web/ be served as it is during
// development (the laserdesign.zip it points to is made by the build).
window.LASERDESIGN_CONFIG = {
  pyodideIndexURL: "https://cdn.jsdelivr.net/pyodide/v314.0.7/full/",
  packageURL: "laserdesign.zip",
};
