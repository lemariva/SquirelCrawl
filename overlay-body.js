window.addEventListener("load", function() {
	var overlay = new Overlay(document.getElementById("overlay"));
	document.getElementById("#overlay#").addEventListener('submit', function (ev) {
		ev.preventDefault(); // to stop the form from submitting
		overlay.show();
	}, false);
});
