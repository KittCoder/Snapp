/* Onboarding and the store locator share the same verified store selection. */
(() => {
  const input = document.getElementById('onboarding-store');
  const zip = document.getElementById('onboarding-zip-code');
  const status = document.getElementById('onboarding-store-status');
  const retry = document.getElementById('onboarding-store-retry');
  function render() {
    const stores = window.SNAPP_STORES.stores;
    const ranked = window.SNAPP_RANK_STORES ? window.SNAPP_RANK_STORES(stores, zip.value.trim()) : stores;
    input.replaceChildren();
    const placeholder = document.createElement('option');
    placeholder.value = ''; placeholder.textContent = 'Select your grocery store'; input.append(placeholder);
    for (const store of ranked) {
      const option = document.createElement('option'); option.value = store.id;
      option.textContent = [store.store_name, store.address].filter(Boolean).join(' — ');
      input.append(option);
    }
    input.value = window.SNAPP_ACTIVE_STORE.id || '';
    input.disabled = !stores.length;
    status.textContent = stores.length ? 'Your selected location supplies Home deals and grocery prices.' : 'Stores unavailable. Retry to choose your location.';
    retry.hidden = Boolean(stores.length);
  }
  input.addEventListener('change', () => { if (input.value) window.SNAPP_ACTIVE_STORE.select(input.value); });
  zip.addEventListener('input', render);
  retry.addEventListener('click', () => window.SNAPP_STORES.load());
  document.addEventListener('snapp:active-store', render);
  window.SNAPP_STORES.subscribe(() => {
    render();
    renderHomeForAuthState();
    if (currentUser && !isAccountSetupPending() && isOnboardingRequired()) {
      if (currentUserInfo) syncOnboardingFromUserInfo(currentUserInfo);
      showPanel(ONBOARDING_PANEL_ID);
    }
  });
})();
