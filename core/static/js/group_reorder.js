// Shared drag-to-reorder for the Groups panel.
// Expects:
//   <ul id="groups-list">
//     <li data-group-name="..."> <a class="group-link"> Group Display Name </a> </li>
//   </ul>
// Initialise via initGroupReorder({ saveUrl, csrfToken }).
(function () {
  function getGroupName(li) {
    var a = li.querySelector('.group-link');
    if (!a) return '';
    // Use text content stripped (icon nodes are inside <i>; remove those by reading direct text)
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

  window.initGroupReorder = function (opts) {
    var list = document.getElementById('groups-list');
    if (!list) return;
    if (!opts || !opts.saveUrl) return;

    if (!document.getElementById('group-reorder-style')) {
      var style = document.createElement('style');
      style.id = 'group-reorder-style';
      style.textContent =
        '#groups-list > li.group-draggable { cursor: grab; }' +
        '#groups-list > li.group-draggable:active { cursor: grabbing; }' +
        '#groups-list > li.dragging { opacity: 0.5; }';
      document.head.appendChild(style);
    }

    var dragged = null;

    Array.from(list.querySelectorAll(':scope > li')).forEach(function (li) {
      li.setAttribute('draggable', 'true');
      li.classList.add('group-draggable');

      li.addEventListener('dragstart', function (e) {
        dragged = li;
        li.classList.add('dragging');
        try { e.dataTransfer.effectAllowed = 'move'; } catch (_) {}
        try { e.dataTransfer.setData('text/plain', ''); } catch (_) {}
      });

      li.addEventListener('dragend', function () {
        if (dragged) dragged.classList.remove('dragging');
        dragged = null;
        list.querySelectorAll('.drop-target').forEach(function (n) { n.classList.remove('drop-target'); });
      });

      li.addEventListener('dragover', function (e) {
        if (!dragged || dragged === li) return;
        e.preventDefault();
        try { e.dataTransfer.dropEffect = 'move'; } catch (_) {}
        var rect = li.getBoundingClientRect();
        var before = (e.clientY - rect.top) < rect.height / 2;
        if (before) list.insertBefore(dragged, li);
        else list.insertBefore(dragged, li.nextSibling);
      });

      li.addEventListener('drop', function (e) {
        e.preventDefault();
        var order = readOrder(list);
        postOrder(opts.saveUrl, opts.csrfToken, order).catch(function () {
          // On failure, reload to get the canonical order back
          window.location.reload();
        });
      });
    });
  };
})();
