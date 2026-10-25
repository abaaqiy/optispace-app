/* Uses the searchable select already bundled with Django admin. */
(() => {
  const $ = window.django.jQuery;
  const otherRoom = '__other__';
  const normalise = (value) => value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();

  function initialise(root) {
    $(root).find('select.room-catalog-select').each(function () {
      const select = $(this);
      if (select.hasClass('select2-hidden-accessible')) return;

      select.select2({
        theme: 'admin-autocomplete',
        dropdownCssClass: 'room-catalog-dropdown',
        width: '100%',
        minimumResultsForSearch: 0,
        matcher: (params, data) => {
          if (data.id === otherRoom) return data;
          const words = normalise(params.term || '').trim().split(/\s+/);
          return words.every((word) => normalise(data.text).includes(word)) ? data : null;
        },
        language: { noResults: () => 'No matching option found.' },
      });

      const label = document.querySelector(`label[for="${this.id}"]`);
      if (label) {
        label.id ||= `${this.id}_label`;
        select.next('.select2').find('.select2-selection').attr('aria-labelledby', label.id);
      }

      select.on('select2:open', () => {
        document.querySelector('.select2-container--open .select2-search__field')?.focus();
      });
    });

    $(root).find('.room-name-widget').each(function () {
      const select = this.querySelector('select');
      const container = this.querySelector('.room-custom-name');
      const input = container.querySelector('input');
      const update = (focus = false) => {
        const custom = select.value === otherRoom;
        container.hidden = !custom;
        input.disabled = !custom;
        input.required = custom;
        if (custom && focus) input.focus();
      };
      $(select).off('change.roomName').on('change.roomName', () => update(true));
      update();
    });
  }

  $(function () { initialise(document); });
  document.addEventListener('formset:added', (event) => initialise(event.target));
})();
