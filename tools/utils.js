const URL_PROFILE = "https://h5sdk.joynetgame.com";
// https://jsonformatter.curiousconcept.com/

function deepParse(value) {
    if (typeof value === "string") {
        try {
            return deepParse(JSON.parse(value));
        } catch {
            return value;
        }
    }

    if (Array.isArray(value)) {
        return value.map(deepParse);
    }

    if (value && typeof value === "object") {
        for (const key in value) {
            value[key] = deepParse(value[key]);
        }
    }

    return value;
}

const saveLocalStorage = () => deepParse(JSON.stringify(localStorage));

function restoreLocalStorage(data) {
    for (const [key, value] of Object.entries(data)) {
        localStorage.setItem(
            key,
            typeof value === "string" ? value : JSON.stringify(value),
        );
    }
}

function updateAuthLocalStorage(newAuth) {
    const authEntries = Object.entries(newAuth);

    const allLoginListSuffix = "_allLoginList";
    const allLoginListKeys = Object.keys(localStorage).filter((key) =>
        key.endsWith(allLoginListSuffix),
    );

    const allLoginListKey = allLoginListKeys[0];
    const storagePrefix = allLoginListKey.slice(0, -allLoginListSuffix.length);
    const userLoginDataKey = `${storagePrefix}_userLoginData`;
    const allLoginList = JSON.parse(localStorage.getItem(allLoginListKey));

    for (const [username, auth] of authEntries) {
        allLoginList.value[username] = auth;
    }
    localStorage.setItem(allLoginListKey, JSON.stringify(allLoginList));

    const [, activeAuth] = authEntries.at(-1);
    localStorage.setItem(
        userLoginDataKey,
        JSON.stringify({ value: activeAuth }),
    );

    return;
}
