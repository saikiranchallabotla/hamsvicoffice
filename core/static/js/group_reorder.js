// Drag-to-reorder for the Groups panel.
// Provides a visible drop-position indicator (colored line) and smooth
// FLIP animation when items reflow.
//
// Expects:
//   <ul id="groups-list">
//     <li data-group-name="..."> <a class="group-link"> Group Name </a> </li>
//   </ul>
// Initialise via initGroupReorder({ saveUrl, csrfToken }).
(function () {
  function getGroupName(li) {
    var a = li.querySelector('.group-link');
    if (!a) return '';
    var clone = a.cloneNode(true);
    clone.querySelectorAll('i, span.group-custom-tag').forEach(function (n) { n.remove(); });
    return (clone.textContent || '').trim();
  }

  function readOrder(list) {
    return Array.from(list.querySelectorAll(':scope > li')).map(getGroupName).filter(Boolean);
  }

  function postOrder(saveUrl, csrfToken, order) {
    return fetch(saveUrl, {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrfToken,
      },
      body: JSON.stringify({ order: order }),
    });
  }

  function injectStyles() {
    if (document.getElementById('group-reorder-style')) return;
    var style = document.createElement('style');
    style.id = 'group-reorder-style';
    style.textContent = [
      '#groups-list > li.group-draggable { cursor: grab; transition: transform 180ms ease, opacity 120ms ease; }',
      '#groups-list > li.group-draggable:active { cursor: grabbing; }',
      '#groups-list > li.gr-dragging { opacity: 0.35; transform: scale(0.97); }',
      '#groups-list > li.gr-dragging .group-link { box-shadow: 0 4px 14px rgba(99, 102, 241, 0.35); border-color: #6366f1; background: #eef2ff; color: #4338ca; }',
      '#groups-list .gr-drop-indicator { height: 0; border-top: 3px solid #6366f1; border-radius: 2px; margin: 2px 0; box-shadow: 0 0 6px rgba(99,102,241,0.6); pointer-events: none; list-style: none; }',
    ].join('\n');
    document.head.appendChild(style);
  }

  // Capture positions before DOM change, then animate from old to new (FLIP).
  function flipAnimate(items, fn) {
    var before = items.map(function (el) { return el.getBoundingClientRect(); });
    fn();
    var after = items.map(function (el) { return el.getBoundingClientRect(); });
    items.forEach(function (el, i) {
      var dy = before[i].top - after[i].top;
      if (!dy) return;
      el.style.transition = 'none';
      el.style.transform = 'translateY(' + dy + 'px)';
      // Force reflow then animate to identity
      void el.offsetWidth;
      el.style.transition = 'transform 180ms ease';
      el.style.transform = '';
    });
  }

  window.initGroupReorder = function (opts) {
    var list = document.getElementById('groups-list');
    if (!list) return;
    if (!opts || !opts.saveUrl) return;

    injectStyles();

    var dragged = null;
    var indicator = document.createElement('li');
    indicator.className = 'gr-drop-indicator';

    function clearIndicator() {
      if (indicator.parentNode) indicator.parentNode.removeChild(indicator);
    }

    function siblingsExceptDragged() {
      return Array.from(list.querySelectorAll(':scope > li')).filter(function (n) {
        return n !== dragged && n !== indicator;
      });
    }

    Array.from(list.querySelectorAll(':scope > li')).forEach(function (li) {
      li.setAttribute('draggable', 'true');
      li.classList.add('group-draggable');
    });

    list.addEventListener('dragstart', function (e) {
      var li = e.target.closest('li');
      if (!li || li.parentNode !== list) return;
      dragged = li;
      // Defer the class so the browser captures the drag image first
      setTimeout(function () { li.classList.add('gr-dragging'); }, 0);
      try { e.dataTransfer.effectAllowed = 'move'; } catch (_) {}
      try { e.dataTransfer.setData('text/plain', getGroupName(li)); } catch (_) {}
    });

    list.addEventListener('dragover', function (e) {
      if (!dragged) return;
      e.preventDefault();
      try { e.dataTransfer.dropEffect = 'move'; } catch (_) {}

      var li = e.target.closest('li');
      // If hovering empty space at end of list, place indicator at end
      if (!li || li === indicator || li === dragged || li.parentNode !== list) {
        // Append indicator at end if pointer below last sibling
        var last = list.lastElementChild;
        if (last && last !== indicator) {
          var lr = last.getBoundingClientRect();
          if (e.clientY > lr.bottom - 4) {
            list.appendChild(indicator);
          }
        }
        return;
      }
      var rect = li.getBoundingClientRect();
      var before = (e.clientY - rect.top) < rect.height / 2;
      if (before) {
        if (li.previousSibling !== indicator) list.insertBefore(indicator, li);
      } else {
        if (li.nextSibling !== indicator) list.insertBefore(indicator, li.nextSibling);
      }
    });

    list.addEventListener('dragleave', function (e) {
      // Only clear if leaving the whole list
      if (e.target === list && !list.contains(e.relatedTarget)) {
        clearIndicator();
      }
    });

    list.addEventListener('drop', function (e) {
      if (!dragged) return;
      e.preventDefault();
      var dropPoint = indicator.parentNode === list ? indicator : null;
      var sibs = siblingsExceptDragged();
      sibs.push(dragged);
      flipAnimate(sibs, function () {
        if (dropPoint) {
          list.insertBefore(dragged, dropPoint);
        }
        clearIndicator();
      });
      var order = readOrder(list);
      postOrder(opts.saveUrl, opts.csrfToken, order).catch(function () {
        window.location.reload();
      });
    });

    list.addEventListener('dragend', function () {
      if (dragged) dragged.classList.remove('gr-dragging');
      dragged = null;
      clearIndicator();
    });
  };
})();
