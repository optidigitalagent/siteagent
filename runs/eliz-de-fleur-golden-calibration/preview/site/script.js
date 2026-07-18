(() => {
  "use strict";

  const navToggle = document.querySelector(".nav-toggle");
  const nav = document.querySelector("[data-nav]");

  const setNavState = (isOpen) => {
    if (!navToggle || !nav) return;
    navToggle.setAttribute("aria-expanded", String(isOpen));
    nav.classList.toggle("is-open", isOpen);
    document.body.classList.toggle("nav-open", isOpen);
  };

  navToggle?.addEventListener("click", () => {
    setNavState(navToggle.getAttribute("aria-expanded") !== "true");
  });

  nav?.addEventListener("click", (event) => {
    if (event.target.closest("a")) setNavState(false);
  });

  const desktopNavigation = window.matchMedia("(min-width: 56.0625rem)");
  const closeNavAtDesktop = (event) => {
    if (event.matches) setNavState(false);
  };
  desktopNavigation.addEventListener?.("change", closeNavAtDesktop);

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      setNavState(false);
      navToggle?.focus();
    }
  });

  const videoShell = document.querySelector("[data-video-shell]");
  const video = videoShell?.querySelector("video");
  const videoState = videoShell?.querySelector(".video-state");

  if (video && videoShell && videoState) {
    video.addEventListener("loadstart", () => {
      videoState.textContent = document.documentElement.lang === "en" ? "Loading the film…" : "Ładowanie filmu z realizacji…";
      videoShell.classList.remove("is-ready");
    });
    video.addEventListener("canplay", () => {
      videoState.textContent = document.documentElement.lang === "en" ? "The film is ready to play." : "Film jest gotowy do odtworzenia.";
      videoShell.classList.add("is-ready");
    });
    video.addEventListener("playing", () => {
      videoShell.classList.add("is-playing");
    });
    video.addEventListener("pause", () => {
      videoShell.classList.remove("is-playing");
    });
    video.addEventListener("error", () => {
      videoState.textContent = document.documentElement.lang === "en" ? "The film is temporarily unavailable; the poster remains visible." : "Film jest chwilowo niedostępny; pozostawiamy widoczny kadr realizacji.";
      videoShell.classList.remove("is-ready", "is-playing");
    });
  }

  const form = document.querySelector("[data-inquiry-form]");
  const prepared = document.querySelector("[data-prepared]");
  const preparedText = document.querySelector("[data-prepared-text]");
  const formStatus = document.querySelector("[data-form-status]");
  const copyButton = document.querySelector("[data-copy-message]");
  const instagramProfile = "https://www.instagram.com/eliz_de_fleur/";

  const copyInquiry = async (text) => {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch (_) {
      const helper = document.createElement("textarea");
      helper.value = text;
      helper.setAttribute("readonly", "");
      helper.style.position = "fixed";
      helper.style.opacity = "0";
      document.body.append(helper);
      helper.select();
      const copied = document.execCommand("copy");
      helper.remove();
      return copied;
    }
  };

  const sendInquiry = async (text) => {
    const english = document.documentElement.lang === "en";
    if (navigator.share) {
      try {
        await navigator.share({
          title: english ? "Project enquiry for Eliz de Fleur" : "Zapytanie projektowe do Eliz de Fleur",
          text
        });
        return { kind: "shared", message: english ? "The send window was completed." : "Okno wysyłania zostało zakończone." };
      } catch (error) {
        if (error?.name === "AbortError") {
          return { kind: "cancelled", message: english ? "Sending was cancelled. Your enquiry remains below." : "Wysyłanie anulowano. Treść zapytania pozostaje poniżej." };
        }
      }
    }

    const profileWindow = window.open(instagramProfile, "_blank", "noopener,noreferrer");
    const copied = await copyInquiry(text);
    if (copied && profileWindow) {
      return { kind: "fallback", message: english ? "The enquiry was copied and the Eliz de Fleur profile opened. Paste it into your message and send." : "Zapytanie zostało skopiowane, a profil Eliz de Fleur otwarty. Wklej treść do wiadomości i wyślij." };
    }
    if (copied) {
      return { kind: "fallback", message: english ? "The enquiry was copied. Open @eliz_de_fleur, paste it into a message and send." : "Zapytanie zostało skopiowane. Otwórz @eliz_de_fleur, wklej je do wiadomości i wyślij." };
    }
    return { kind: "manual", message: english ? "Choose Copy enquiry below, then open @eliz_de_fleur and send the message." : "Wybierz „Skopiuj zapytanie” poniżej, potem otwórz @eliz_de_fleur i wyślij wiadomość." };
  };

  const errorMessages = {
    pl: {
      name: "Podaj imię i nazwisko.",
      email: "Podaj poprawny adres e-mail.",
      event: "Wybierz rodzaj projektu.",
      message: "Opisz przestrzeń i kontekst projektu (minimum 20 znaków)."
    },
    en: {
      name: "Enter your name.",
      email: "Enter a valid email address.",
      event: "Choose a project type.",
      message: "Describe the space and project context (at least 20 characters)."
    }
  };

  const showFieldError = (field) => {
    const error = document.getElementById(`${field.name}-error`);
    field.setAttribute("aria-invalid", String(!field.validity.valid));
    const language = document.documentElement.lang === "en" ? "en" : "pl";
    if (error) error.textContent = field.validity.valid ? "" : errorMessages[language][field.name];
  };

  form?.querySelectorAll("input, select, textarea").forEach((field) => {
    field.addEventListener("blur", () => showFieldError(field));
    field.addEventListener("input", () => {
      if (field.getAttribute("aria-invalid") === "true") showFieldError(field);
    });
  });

  form?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const fields = [...form.querySelectorAll("input, select, textarea:not([readonly])")];
    fields.forEach(showFieldError);

    if (!form.checkValidity()) {
      const firstInvalid = form.querySelector(":invalid");
      firstInvalid?.focus();
      return;
    }

    const data = new FormData(form);
    const english = document.documentElement.lang === "en";
    const message = english
      ? ["Hello, I would like to discuss a project with Eliz de Fleur.", "", `Name: ${data.get("name")}`, `Email: ${data.get("email")}`, `Project type: ${data.get("event")}`, `Space and context: ${data.get("message")}`].join("\n")
      : ["Dzień dobry, chciałabym/chciałbym omówić projekt z Eliz de Fleur.", "", `Imię i nazwisko: ${data.get("name")}`, `E-mail: ${data.get("email")}`, `Rodzaj projektu: ${data.get("event")}`, `Przestrzeń i kontekst: ${data.get("message")}`].join("\n");

    if (preparedText) preparedText.value = message;
    if (prepared) prepared.hidden = false;
    const submitButton = form.querySelector("[type='submit']");
    submitButton?.setAttribute("aria-busy", "true");
    if (submitButton) submitButton.disabled = true;
    const result = await sendInquiry(message);
    if (formStatus) {
      formStatus.textContent = result.message;
      formStatus.dataset.state = result.kind === "shared" || result.kind === "fallback" ? "success" : result.kind;
    }
    submitButton?.removeAttribute("aria-busy");
    if (submitButton) submitButton.disabled = false;
    prepared?.scrollIntoView({ behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "nearest" });
    prepared?.focus?.();
  });

  copyButton?.addEventListener("click", async () => {
    if (!preparedText) return;
    let copied = false;

    copied = await copyInquiry(preparedText.value);

    if (formStatus) {
      const english = document.documentElement.lang === "en";
      formStatus.textContent = copied
        ? (english ? "Brief copied. You can now open the @eliz_de_fleur profile." : "Wiadomość została skopiowana. Możesz teraz otworzyć profil @eliz_de_fleur.")
        : (english ? "Automatic copying failed. Select the text and copy it manually." : "Nie udało się skopiować automatycznie. Zaznacz tekst i skopiuj go ręcznie.");
    }
  });

  const multiPageMenuButton = document.querySelector(".menu-toggle");
  const multiPageMenu = document.querySelector(".site-nav");

  const setMultiPageMenu = (isOpen) => {
    if (!multiPageMenuButton || !multiPageMenu) return;
    multiPageMenuButton.setAttribute("aria-expanded", String(isOpen));
    multiPageMenu.classList.toggle("is-open", isOpen);
    document.body.classList.toggle("nav-open", isOpen);
  };

  multiPageMenuButton?.addEventListener("click", () => {
    setMultiPageMenu(multiPageMenuButton.getAttribute("aria-expanded") !== "true");
  });

  multiPageMenu?.addEventListener("click", (event) => {
    if (event.target.closest("a")) setMultiPageMenu(false);
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && multiPageMenuButton?.getAttribute("aria-expanded") === "true") {
      setMultiPageMenu(false);
      multiPageMenuButton.focus();
    }
  });

  window.matchMedia("(min-width: 56.0625rem)").addEventListener?.("change", (event) => {
    if (event.matches) setMultiPageMenu(false);
  });

  const languageButtons = [...document.querySelectorAll("[data-lang]")];
  document.querySelectorAll("[data-en]:not([data-pl])").forEach((element) => {
    element.dataset.pl = element.textContent;
  });
  document.querySelectorAll("[data-en-html]:not([data-pl-html])").forEach((element) => {
    element.dataset.plHtml = element.innerHTML;
  });

  const setLanguage = (language, persist = true) => {
    document.documentElement.lang = language;
    const pageName = window.location.pathname.split("/").pop() || "index.html";
    const metadata = {
      "index.html": {
        title: "Eliz de Fleur — event scenography and floral installations",
        description: "Eliz de Fleur creates event scenography and floral installations for commercial spaces, corporate events, weddings and private celebrations in Warsaw."
      },
      "services.html": {
        title: "Services — Eliz de Fleur | Warsaw",
        description: "Explore Eliz de Fleur services for commercial spaces, corporate events, weddings, private celebrations, photo zones and installations in Warsaw."
      },
      "portfolio.html": {
        title: "Portfolio — Eliz de Fleur | Warsaw",
        description: "Browse Eliz de Fleur event scenography, floral installations, corporate settings, weddings and photo zones in Warsaw."
      },
      "about.html": {
        title: "About — Eliz de Fleur | Warsaw",
        description: "Discover the material, spatial approach behind Eliz de Fleur event scenography and floral installations in Warsaw."
      },
      "contact.html": {
        title: "Contact — Eliz de Fleur | Warsaw",
        description: "Prepare an enquiry about event scenography or a floral installation by Eliz de Fleur in Warsaw and open the @eliz_de_fleur profile."
      }
    }[pageName];
    const description = document.querySelector('meta[name="description"]');
    document.documentElement.dataset.plTitle ||= document.title;
    if (description) description.dataset.plContent ||= description.content;
    if (language === "en" && metadata) {
      document.title = metadata.title;
      if (description) description.content = metadata.description;
    } else {
      document.title = document.documentElement.dataset.plTitle;
      if (description) description.content = description.dataset.plContent;
    }
    document.querySelectorAll("[data-pl][data-en]").forEach((element) => {
      element.textContent = element.dataset[language];
    });
    document.querySelectorAll("[data-pl-html][data-en-html]").forEach((element) => {
      element.innerHTML = element.dataset[`${language}Html`];
    });
    document.querySelectorAll("[data-pl-aria-label][data-en-aria-label]").forEach((element) => {
      element.setAttribute("aria-label", element.dataset[`${language}AriaLabel`]);
    });
    document.querySelectorAll(".site-nav, .main-nav").forEach((navigation) => {
      navigation.setAttribute("aria-label", language === "en" ? "Main navigation" : "Główna nawigacja");
    });
    document.querySelectorAll(".portfolio-filters").forEach((filters) => {
      filters.setAttribute("aria-label", language === "en" ? "Portfolio filters" : "Filtry portfolio");
    });
    document.querySelectorAll(".brief-output").forEach((output) => {
      output.setAttribute("aria-label", language === "en" ? "Prepared enquiry" : "Przygotowane zapytanie");
    });
    document.querySelectorAll("video[aria-label]").forEach((video) => {
      video.dataset.plLabel ||= video.getAttribute("aria-label");
      const isPhotoZone = /etno|zdję/i.test(video.dataset.plLabel);
      video.setAttribute(
        "aria-label",
        language === "en"
          ? (isPhotoZone ? "Video of an ethno-style photo zone" : "Video of red event scenography")
          : video.dataset.plLabel
      );
    });
    const translateAlt = (polishAlt) => {
      if (/Stała instalacja|instalacji roślinnej/i.test(polishAlt)) return "Permanent plant installation by Eliz de Fleur in Warsaw";
      if (/Świąteczny stół|stołu firmowego/i.test(polishAlt)) return "Corporate holiday table arrangement by Eliz de Fleur";
      if (/niebieskim akcentem/i.test(polishAlt)) return "Celebration arrangement with a blue accent by Eliz de Fleur";
      if (/Czerwona scenografia|czerwonej scenografii/i.test(polishAlt)) return "Red event scenography by Eliz de Fleur";
      if (/Strefa zdjęć/i.test(polishAlt)) return "Ethno-style photo zone by Eliz de Fleur";
      return polishAlt;
    };
    document.querySelectorAll("img[alt]").forEach((image) => {
      image.dataset.plAlt ||= image.getAttribute("alt");
      image.setAttribute("alt", language === "en" ? translateAlt(image.dataset.plAlt) : image.dataset.plAlt);
    });
    languageButtons.forEach((button) => button.setAttribute("aria-pressed", String(button.dataset.lang === language)));
    if (persist) {
      try { window.localStorage.setItem("eliz-language", language); } catch (_) { /* Preference storage is optional. */ }
    }
  };

  languageButtons.forEach((button) => {
    button.addEventListener("click", () => setLanguage(button.dataset.lang));
  });

  if (languageButtons.length) {
    let preferredLanguage = new URLSearchParams(window.location.search).get("lang");
    if (!preferredLanguage) {
      try { preferredLanguage = window.localStorage.getItem("eliz-language"); } catch (_) { preferredLanguage = null; }
    }
    setLanguage(preferredLanguage === "en" ? "en" : "pl", false);
  }

  const portfolioFilters = [...document.querySelectorAll(".portfolio-filters [data-filter]")];
  const portfolioItems = [...document.querySelectorAll(".media-item[data-category]")];

  portfolioFilters.forEach((button) => {
    button.addEventListener("click", () => {
      const filter = button.dataset.filter;
      portfolioFilters.forEach((candidate) => {
        const active = candidate === button;
        candidate.classList.toggle("is-active", active);
        candidate.setAttribute("aria-pressed", String(active));
      });
      portfolioItems.forEach((item) => {
        item.hidden = filter !== "all" && item.dataset.category !== filter;
      });
    });
  });

  const briefForm = document.querySelector(".brief-form");
  const briefError = briefForm?.querySelector(".form-error");
  const briefResult = briefForm?.querySelector(".form-result");
  const briefOutput = briefForm?.querySelector(".brief-output");
  const briefCopy = briefForm?.querySelector(".copy-brief");
  const briefCopyStatus = briefForm?.querySelector(".copy-status");
  const briefState = briefForm?.querySelector(".form-result__state");
  const requiredBriefControls = [...(briefForm?.querySelectorAll("[required]") || [])];

  requiredBriefControls.forEach((control) => {
    control.addEventListener("invalid", () => control.setAttribute("aria-invalid", "true"));
    control.addEventListener("input", () => {
      if (control.validity.valid) control.removeAttribute("aria-invalid");
    });
  });

  briefForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!briefForm.checkValidity()) {
      if (briefError) briefError.textContent = document.documentElement.lang === "en" ? "Complete all required fields and enter a valid email." : "Uzupełnij wymagane pola i podaj poprawny adres e-mail.";
      briefForm.querySelector(":invalid")?.focus();
      return;
    }

    if (briefError) briefError.textContent = "";
    requiredBriefControls.forEach((control) => control.removeAttribute("aria-invalid"));
    const data = new FormData(briefForm);
    const english = document.documentElement.lang === "en";
    const preparedBrief = english
      ? [`Hello, I would like to discuss a project with Eliz de Fleur.`, ``, `Name: ${data.get("name")}`, `Email: ${data.get("email")}`, `Project type: ${data.get("event")}`, `Project context: ${data.get("message")}`, `Questions: ${data.get("questions") || "—"}`].join("\n")
      : [`Dzień dobry, chcę omówić projekt z Eliz de Fleur.`, ``, `Imię i nazwisko: ${data.get("name")}`, `E-mail: ${data.get("email")}`, `Rodzaj projektu: ${data.get("event")}`, `Kontekst projektu: ${data.get("message")}`, `Pytania: ${data.get("questions") || "—"}`].join("\n");

    if (briefOutput) briefOutput.value = preparedBrief;
    if (briefResult) briefResult.hidden = false;
    const submitButton = briefForm.querySelector("[type='submit']");
    submitButton?.setAttribute("aria-busy", "true");
    if (submitButton) submitButton.disabled = true;
    const result = await sendInquiry(preparedBrief);
    if (briefState) {
      briefState.textContent = result.message;
      briefState.dataset.state = result.kind === "shared" || result.kind === "fallback" ? "success" : result.kind;
    }
    submitButton?.removeAttribute("aria-busy");
    if (submitButton) submitButton.disabled = false;
    briefResult?.focus();
  });

  briefCopy?.addEventListener("click", async () => {
    if (!briefOutput) return;
    let copied = false;
    copied = await copyInquiry(briefOutput.value);
    if (briefCopyStatus) {
      const english = document.documentElement.lang === "en";
      briefCopyStatus.textContent = copied
        ? (english ? "Brief copied." : "Opis został skopiowany.")
        : (english ? "Select and copy the text manually." : "Zaznacz tekst i skopiuj go ręcznie.");
    }
  });

  document.querySelectorAll("[data-year]").forEach((element) => {
    element.textContent = String(new Date().getFullYear());
  });
})();
