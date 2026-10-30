// Places the "select type" popup of grouped items (Estimate, Workslip,
// Temporary Works, AMC). Beside the tapped item when there is room (desktop),
// otherwise just below or above it - always kept fully inside the screen so it
// is visible on phones, where the item spans the whole width.
(function () {
    'use strict';

    var GAP = 5;
    var EDGE = 8;

    window.positionSubtypesPopup = function (popup, anchor) {
        var rect = anchor.getBoundingClientRect();
        var vw = document.documentElement.clientWidth || window.innerWidth;
        var vh = window.innerHeight;

        popup.style.position = 'fixed';
        popup.style.maxWidth = Math.min(320, vw - EDGE * 2) + 'px';
        popup.classList.add('active');

        var w = popup.offsetWidth;
        var h = popup.offsetHeight;
        var left, top;

        if (rect.right + GAP + w + EDGE <= vw) {
            left = rect.right + GAP;
            top = rect.top;
        } else if (rect.left - GAP - w >= EDGE) {
            left = rect.left - GAP - w;
            top = rect.top;
        } else {
            left = rect.left;
            top = rect.bottom + GAP;
            if (top + h + EDGE > vh && rect.top - GAP - h >= EDGE) {
                top = rect.top - GAP - h;
            }
        }

        left = Math.max(EDGE, Math.min(left, vw - w - EDGE));
        top = Math.max(EDGE, Math.min(top, vh - h - EDGE));
        popup.style.left = left + 'px';
        popup.style.top = top + 'px';
    };
})();
