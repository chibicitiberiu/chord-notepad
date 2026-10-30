// The app's WebView (UserGuideScreen.kt) is sized by Compose with
// wrap_content layout params, so CSS viewport units resolve to 0 there and a
// `max-height: 70vh` image collapses to a dot. The screen size is right, so
// the image height cap comes from it instead (android.css: --img-max-h).
(function () {
    function update() {
        var h = (window.screen && screen.height) || 0;
        if (h > 0) {
            document.documentElement.style.setProperty('--img-max-h', Math.round(h * 0.7) + 'px');
        }
    }
    update();
    window.addEventListener('resize', update);
    window.addEventListener('orientationchange', update);
})();
