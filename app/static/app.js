const wardrobeForm = document.getElementById('wardrobe-form');
const outfitForm = document.getElementById('outfit-form');
const wardrobeList = document.getElementById('wardrobe-list');
const favoritesList = document.getElementById('favorites-list');
const outfitResult = document.getElementById('outfit-result');
const formMessage = document.getElementById('form-message');
const weatherBox = document.getElementById('weather-box');
const langToggle = document.getElementById('lang-toggle');
const statusBox = document.getElementById('status-box');

const translations = {
  ru: {
    appTitle: 'Outfit',
    addItem: 'Добавить вещь',
    name: 'Название',
    add: 'Добавить',
    generate: 'Подобрать',
    city: 'Город',
    style: 'Стиль',
    styleCasual: 'Повседневный',
    styleSporty: 'Спортивный',
    styleMinimal: 'Минималистичный',
    threeOptions: '3 варианта',
    useLocation: 'Моё местоположение',
    getOutfit: 'Получить образ',
    wardrobe: 'Гардероб',
    refresh: 'Обновить',
    refreshFavorites: 'Обновить избранное',
    suggestions: 'Подборки',
    favorites: 'Избранное',
    noClothes: 'Пока нет вещей.',
    noOutfit: 'Пока нет образа.',
    noFavorites: 'Пока нет избранного.',
    delete: 'Удалить',
    save: 'Сохранить',
    option: 'Вариант',
    generating: 'Подбираю образ...',
    favoriteSaved: 'Сохранено в избранное',
    itemAdded: 'Вещь добавлена',
    locationCaptured: 'Местоположение получено. Теперь нажми «Получить образ».',
    locationDenied: 'Не удалось получить местоположение.',
    geolocationUnsupported: 'Геолокация не поддерживается в этом браузере.',
    demoLocation: 'Демо-локация',
    outfitWord: 'образ',
    placeholdersItem: 'Белая футболка',
    placeholdersCity: 'Innopolis',
    styleMap: { casual: 'Повседневный', sporty: 'Спортивный', minimal: 'Минималистичный' },
    typeUnknown: 'Не удалось определить категорию вещи. Попробуй назвать вещь понятнее.',
    requestFailed: 'Ошибка запроса',
    modeRules: 'Логика',
    modeLlm: 'LLM',
    weatherSource: 'Погода',
    weatherDemo: 'Демо',
    selected: 'Выбрано',
  },
  en: {
    appTitle: 'Outfit',
    addItem: 'Add item',
    name: 'Name',
    add: 'Add',
    generate: 'Generate',
    city: 'City',
    style: 'Style',
    styleCasual: 'Casual',
    styleSporty: 'Sporty',
    styleMinimal: 'Minimal',
    threeOptions: '3 options',
    useLocation: 'Use location',
    getOutfit: 'Get outfit',
    wardrobe: 'Wardrobe',
    refresh: 'Refresh',
    refreshFavorites: 'Refresh favorites',
    suggestions: 'Suggestions',
    favorites: 'Favorites',
    noClothes: 'No clothes yet.',
    noOutfit: 'No outfit generated yet.',
    noFavorites: 'No favorites saved yet.',
    delete: 'Delete',
    save: 'Save',
    option: 'Option',
    generating: 'Generating outfit...',
    favoriteSaved: 'Favorite saved',
    itemAdded: 'Item added',
    locationCaptured: 'Location captured. Now press Get outfit.',
    locationDenied: 'Could not access your location.',
    geolocationUnsupported: 'Geolocation is not supported in this browser.',
    demoLocation: 'Demo location',
    outfitWord: 'outfit',
    placeholdersItem: 'White T-shirt',
    placeholdersCity: 'Innopolis',
    styleMap: { casual: 'Casual', sporty: 'Sporty', minimal: 'Minimal' },
    typeUnknown: 'Could not detect item category. Try a clearer item name.',
    requestFailed: 'Request failed',
    modeRules: 'Rules',
    modeLlm: 'LLM',
    weatherSource: 'Weather',
    weatherDemo: 'Demo',
    selected: 'Selected',
  }
};

const topWords = ['t-shirt', 'tee', 'shirt', 'hoodie', 'sweater', 'jumper', 'top', 'polo', 'blouse', 'cardigan', 'longsleeve', 'long sleeve', 'sweatshirt', 'thermal', 'fleece', 'майк', 'футбол', 'рубаш', 'худи', 'свитер', 'кофта', 'поло', 'блуз', 'кардиган', 'лонгслив', 'толстов', 'термо', 'флис'];
const bottomWords = ['jeans', 'trousers', 'pants', 'joggers', 'shorts', 'skirt', 'leggings', 'cargo', 'chinos', 'sweatpants', 'джинс', 'брюк', 'штаны', 'джоггер', 'шорты', 'юбка', 'леггин', 'карго', 'чинос', 'спортивн'];
const shoesWords = ['sneakers', 'boots', 'shoes', 'trainers', 'loafers', 'sandals', 'flip-flops', 'flip flops', 'slides', 'slippers', 'mules', 'heels', 'кроссов', 'ботин', 'туфл', 'обув', 'сандал', 'сланц', 'шлеп', 'шлёп', 'тапк', 'сабо', 'каблу'];
const jacketWords = ['jacket', 'coat', 'windbreaker', 'parka', 'blazer', 'raincoat', 'trench', 'bomber', 'puffer', 'down jacket', 'overshirt', 'denim jacket', 'vest', 'anorak', 'куртк', 'пальто', 'ветров', 'парка', 'пиджак', 'плащ', 'тренч', 'бомбер', 'пухов', 'джинсовк', 'жилет', 'анорак'];
const accessoryWords = ['hat', 'cap', 'beanie', 'gloves', 'mittens', 'scarf', 'shawl', 'sunglasses', 'umbrella', 'bucket hat', 'panama', 'кепк', 'шапк', 'перчат', 'вареж', 'шарф', 'палантин', 'очки', 'зонт', 'панама'];

let currentLang = localStorage.getItem('lang') || 'ru';
let geoPayload = null;
let lastGenerated = null;
let config = null;

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.detail || t('requestFailed'));
  }
  return data;
}

function t(key) {
  return translations[currentLang][key] || key;
}

function inferType(name) {
  const value = name.toLowerCase();
  if (topWords.some(word => value.includes(word))) return 'top';
  if (bottomWords.some(word => value.includes(word))) return 'bottom';
  if (shoesWords.some(word => value.includes(word))) return 'shoes';
  if (jacketWords.some(word => value.includes(word))) return 'jacket';
  if (accessoryWords.some(word => value.includes(word))) return 'accessory';
  return null;
}

function translateError(message) {
  if (currentLang !== 'ru') return message;
  return message
    .replace('Request failed', 'Ошибка запроса')
    .replace('City', 'Город')
    .replace('was not found', 'не найден')
    .replace('Not enough wardrobe items. Please add at least one item for:', 'Недостаточно вещей в гардеробе. Добавь хотя бы по одной вещи в категории:')
    .replace('top', 'верх')
    .replace('bottom', 'низ')
    .replace('shoes', 'обувь')
    .replace('jacket', 'верхняя одежда')
    .replace('Could not build an outfit from the wardrobe.', 'Не удалось собрать образ из текущего гардероба.')
    .replace('Wardrobe is empty. Add some clothes first.', 'Гардероб пуст. Сначала добавь вещи.');
}

function applyLanguage() {
  document.documentElement.lang = currentLang;
  document.title = t('appTitle');
  langToggle.textContent = currentLang === 'ru' ? 'EN' : 'RU';

  document.querySelectorAll('[data-i18n]').forEach((node) => {
    const key = node.dataset.i18n;
    node.textContent = t(key);
  });

  document.getElementById('item-name').placeholder = t('placeholdersItem');
  document.getElementById('city').placeholder = t('placeholdersCity');

  if (config) renderStatus();
  if (lastGenerated) {
    renderWeather(lastGenerated.weather, lastGenerated.generation_mode);
    renderOutfits(lastGenerated);
  }
}

function setMessage(message, isError = false) {
  formMessage.textContent = isError ? translateError(message) : message;
  formMessage.classList.toggle('error', isError);
}

function renderStatus() {
  if (!config) {
    statusBox.innerHTML = '';
    return;
  }
  const llmText = config.llm_enabled ? `${t('modeLlm')}: ${config.llm_model || 'on'}` : `${t('modeLlm')}: off`;
  statusBox.innerHTML = `
    <span class="badge">${llmText}</span>
    <span class="badge">${t('weatherSource')}: ${config.weather_provider}</span>
  `;
}

function renderWardrobe(items) {
  if (!items.length) {
    wardrobeList.className = 'wardrobe-list empty-state';
    wardrobeList.textContent = t('noClothes');
    return;
  }

  wardrobeList.className = 'wardrobe-list';
  wardrobeList.innerHTML = items.map(item => `
    <div class="item-chip">
      <div class="item-meta">
        <strong>${item.name}</strong>
      </div>
      <button class="danger" onclick="deleteItem(${item.id})">${t('delete')}</button>
    </div>
  `).join('');
}

function renderWeather(weather, generationMode) {
  weatherBox.classList.remove('hidden');
  const modeLabel = generationMode === 'llm' ? t('modeLlm') : t('modeRules');
  const sourceLabel = weather.source === 'demo' ? t('weatherDemo') : weather.provider;
  weatherBox.innerHTML = `
    <div class="weather-topline">
      <span class="badge">${modeLabel}</span>
      <span class="badge">${t('weatherSource')}: ${sourceLabel}</span>
    </div>
    <div>${weather.summary}</div>
  `;
}

function renderOutfits(data) {
  const options = data.options || [];
  if (!options.length) {
    outfitResult.className = 'stack empty-state';
    outfitResult.textContent = t('noOutfit');
    return;
  }

  outfitResult.className = 'stack';
  outfitResult.innerHTML = options.map((option, index) => {
    const itemNames = option.items.map(item => item.name).join(', ');
    return `
      <div class="outfit-card">
        <div class="section-head">
          <strong>${t('option')} ${index + 1}</strong>
          <button onclick="saveFavorite(${index})">${t('save')}</button>
        </div>
        <div class="outfit-items">
          ${option.items.map(item => `<span class="outfit-item-chip">${item.name}</span>`).join('')}
        </div>
        <div class="outfit-summary">
          <strong>${t('selected')}:</strong>
          <span>${itemNames}</span>
        </div>
        <p class="outfit-explanation">${option.explanation}</p>
      </div>
    `;
  }).join('');
}

function renderFavorites(items) {
  if (!items.length) {
    favoritesList.className = 'stack empty-state';
    favoritesList.textContent = t('noFavorites');
    return;
  }

  favoritesList.className = 'stack';
  favoritesList.innerHTML = items.map(item => `
    <div class="favorite-card">
      <div class="section-head">
        <strong>${translations[currentLang].styleMap[item.style] || item.style} ${t('outfitWord')}</strong>
        <span>${new Date(item.created_at).toLocaleString(currentLang === 'ru' ? 'ru-RU' : 'en-US')}</span>
      </div>
      <div class="badge">${item.city || t('demoLocation')}</div>
      <p>${item.weather_summary}</p>
      <div class="outfit-items">
        ${item.items.map(part => `<span>${part.name}</span>`).join('')}
      </div>
      <p>${item.explanation}</p>
    </div>
  `).join('');
}

async function loadConfig() {
  config = await api('/api/config');
  renderStatus();
}

async function loadWardrobe() {
  const data = await api('/api/wardrobe');
  renderWardrobe(data.items);
}

async function loadFavorites() {
  const data = await api('/api/favorites');
  renderFavorites(data.items);
}

window.deleteItem = async function deleteItem(id) {
  try {
    await api(`/api/wardrobe/${id}`, { method: 'DELETE' });
    await loadWardrobe();
  } catch (error) {
    alert(translateError(error.message));
  }
};

window.saveFavorite = async function saveFavorite(index) {
  if (!lastGenerated) return;
  const option = lastGenerated.options[index];
  try {
    await api('/api/favorites', {
      method: 'POST',
      body: JSON.stringify({
        city: document.getElementById('city').value.trim() || lastGenerated.weather.location,
        style: lastGenerated.style,
        weather_summary: lastGenerated.weather.summary,
        items: option.items,
        explanation: option.explanation,
      })
    });
    await loadFavorites();
    alert(t('favoriteSaved'));
  } catch (error) {
    alert(translateError(error.message));
  }
};

wardrobeForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const name = document.getElementById('item-name').value.trim();

  try {
    await api('/api/wardrobe', {
      method: 'POST',
      body: JSON.stringify({ name })
    });
    wardrobeForm.reset();
    setMessage(t('itemAdded'));
    await loadWardrobe();
  } catch (error) {
    setMessage(error.message, true);
  }
});

outfitForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const payload = {
    city: document.getElementById('city').value.trim() || null,
    style: document.getElementById('style').value,
    multiple: document.getElementById('multiple').checked,
    lang: currentLang,
    ...geoPayload,
  };

  try {
    outfitResult.className = 'stack';
    outfitResult.innerHTML = `<div class="outfit-card">${t('generating')}</div>`;
    const data = await api('/api/generate-outfit', {
      method: 'POST',
      body: JSON.stringify(payload)
    });
    lastGenerated = data;
    renderWeather(data.weather, data.generation_mode);
    renderOutfits(data);
  } catch (error) {
    outfitResult.className = 'stack error';
    outfitResult.textContent = translateError(error.message);
  }
});

document.getElementById('use-location').addEventListener('click', () => {
  if (!navigator.geolocation) {
    alert(t('geolocationUnsupported'));
    return;
  }

  navigator.geolocation.getCurrentPosition(
    (position) => {
      geoPayload = {
        latitude: position.coords.latitude,
        longitude: position.coords.longitude,
      };
      document.getElementById('city').value = '';
      alert(t('locationCaptured'));
    },
    () => alert(t('locationDenied'))
  );
});

document.getElementById('refresh-wardrobe').addEventListener('click', loadWardrobe);
document.getElementById('refresh-favorites').addEventListener('click', loadFavorites);
langToggle.addEventListener('click', () => {
  currentLang = currentLang === 'ru' ? 'en' : 'ru';
  localStorage.setItem('lang', currentLang);
  applyLanguage();
  loadFavorites();
});

applyLanguage();
loadConfig();
loadWardrobe();
loadFavorites();
