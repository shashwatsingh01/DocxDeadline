document.addEventListener("DOMContentLoaded", () => {
  const toggle = document.querySelector("[data-menu-toggle]");
  const sidebar = document.querySelector("[data-sidebar]");
  if (toggle && sidebar) {
    toggle.addEventListener("click", () => sidebar.classList.toggle("is-open"));
  }

  const calendar = document.querySelector("[data-calendar]");
  if (calendar) {
    const month = calendar.dataset.month;
    fetch(`/calendar/events/?month=${month}`)
      .then((response) => response.json())
      .then(({ events }) => {
        events.forEach((event) => {
          const day = calendar.querySelector(`[data-date="${event.date}"] .day-events`);
          if (!day) return;
          const link = document.createElement("a");
          link.className = `calendar-event ${event.type} ${event.status === "completed" ? "completed" : ""}`;
          link.href = event.url;
          link.textContent = event.title;
          link.title = event.title;
          day.appendChild(link);
        });
      })
      .catch(() => {});
  }
});
