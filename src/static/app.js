document.addEventListener("DOMContentLoaded", () => {
  const activitiesList = document.getElementById("activities-list");
  const activitySelect = document.getElementById("activity");
  const signupForm = document.getElementById("signup-form");
  const messageDiv = document.getElementById("message");
  const adminLoginForm = document.getElementById("admin-login-form");
  const adminControls = document.getElementById("admin-controls");
  const adminMessage = document.getElementById("admin-message");
  let isAdmin = false;

  function showMessage(element, message, success) {
    element.textContent = message;
    element.className = `message ${success ? "success" : "error"}`;
    setTimeout(() => element.classList.add("hidden"), 5000);
  }

  async function requestJson(url, options = {}) {
    const response = await fetch(url, options);
    const result = await response.json();
    if (!response.ok) {
      throw new Error(result.detail || "The request could not be completed");
    }
    return result;
  }

  function createTextElement(tag, text, className) {
    const element = document.createElement(tag);
    element.textContent = text;
    if (className) element.className = className;
    return element;
  }

  async function updateActivity(activityName, changes) {
    await requestJson(`/admin/activities/${encodeURIComponent(activityName)}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(changes),
    });
    await fetchActivities();
  }

  function addOrganizerControls(card, activityName, details) {
    const controls = document.createElement("details");
    controls.className = "activity-admin";
    controls.appendChild(createTextElement("summary", "Manage activity"));

    const form = document.createElement("form");
    form.className = "activity-edit-form";
    const fields = [
      ["description", "Description", "text", details.description],
      ["schedule", "Schedule", "text", details.schedule],
      ["max_participants", "Maximum participants", "number", details.max_participants],
    ];
    fields.forEach(([name, labelText, type, value]) => {
      const label = createTextElement("label", labelText);
      const input = document.createElement("input");
      input.name = name;
      input.type = type;
      input.value = value;
      input.required = true;
      if (name === "max_participants") {
        input.min = "1";
        input.max = "500";
      }
      label.appendChild(input);
      form.appendChild(label);
    });
    const saveButton = document.createElement("button");
    saveButton.type = "submit";
    saveButton.textContent = "Save changes";
    form.appendChild(saveButton);
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const formData = new FormData(form);
      try {
        await updateActivity(activityName, {
          description: formData.get("description"),
          schedule: formData.get("schedule"),
          max_participants: Number(formData.get("max_participants")),
        });
        showMessage(adminMessage, `Updated ${activityName}`, true);
      } catch (error) {
        showMessage(adminMessage, error.message, false);
      }
    });
    controls.appendChild(form);

    const statusButton = document.createElement("button");
    statusButton.type = "button";
    statusButton.textContent = details.is_open === false ? "Reopen signups" : "Close signups";
    statusButton.addEventListener("click", async () => {
      try {
        await updateActivity(activityName, { is_open: details.is_open === false });
        showMessage(adminMessage, `Updated signups for ${activityName}`, true);
      } catch (error) {
        showMessage(adminMessage, error.message, false);
      }
    });
    controls.appendChild(statusButton);
    card.appendChild(controls);
  }

  async function fetchActivities() {
    try {
      const activities = await requestJson("/activities");
      activitiesList.replaceChildren();
      activitySelect.replaceChildren(new Option("-- Select an activity --", ""));

      Object.entries(activities).forEach(([name, details]) => {
        const card = document.createElement("div");
        card.className = "activity-card";
        card.appendChild(createTextElement("h4", name));
        card.appendChild(createTextElement("p", details.description));
        card.appendChild(createTextElement("p", `Schedule: ${details.schedule}`));

        const spotsLeft = details.max_participants - details.participants.length;
        const isOpen = details.is_open !== false;
        card.appendChild(
          createTextElement(
            "p",
            `${isOpen ? "Open" : "Closed"} - ${Math.max(0, spotsLeft)} spots left`
          )
        );

        if (details.participants.length) {
          const participantSection = document.createElement("div");
          participantSection.className = "participants-section";
          participantSection.appendChild(createTextElement("h5", "Participants"));
          const list = document.createElement("ul");
          list.className = "participants-list";
          details.participants.forEach((email) => {
            const item = document.createElement("li");
            item.appendChild(createTextElement("span", email, "participant-email"));
            if (isAdmin) {
              const removeButton = document.createElement("button");
              removeButton.type = "button";
              removeButton.className = "delete-btn";
              removeButton.textContent = "Remove";
              removeButton.addEventListener("click", async () => {
                try {
                  await requestJson(
                    `/admin/activities/${encodeURIComponent(name)}/participants/${encodeURIComponent(email)}`,
                    { method: "DELETE" }
                  );
                  await fetchActivities();
                } catch (error) {
                  showMessage(adminMessage, error.message, false);
                }
              });
              item.appendChild(removeButton);
            }
            list.appendChild(item);
          });
          participantSection.appendChild(list);
          card.appendChild(participantSection);
        } else {
          card.appendChild(createTextElement("p", "No participants yet"));
        }

        if (isAdmin) addOrganizerControls(card, name, details);
        activitiesList.appendChild(card);

        const option = new Option(name, name);
        option.disabled = !isOpen || spotsLeft <= 0;
        activitySelect.appendChild(option);
      });
    } catch (error) {
      activitiesList.replaceChildren(
        createTextElement("p", "Failed to load activities. Please try again later.")
      );
    }
  }

  async function refreshAdminState() {
    try {
      const result = await requestJson("/admin/me");
      isAdmin = result.authenticated;
    } catch {
      isAdmin = false;
    }
    adminLoginForm.hidden = isAdmin;
    adminControls.hidden = !isAdmin;
    await fetchActivities();
  }

  adminLoginForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const formData = new FormData(adminLoginForm);
    try {
      await requestJson("/admin/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: formData.get("username"),
          password: formData.get("password"),
        }),
      });
      adminLoginForm.reset();
      showMessage(adminMessage, "Organizer signed in", true);
      await refreshAdminState();
    } catch (error) {
      showMessage(adminMessage, error.message, false);
    }
  });

  document.getElementById("admin-logout").addEventListener("click", async () => {
    try {
      await requestJson("/admin/logout", { method: "POST" });
      showMessage(adminMessage, "Organizer signed out", true);
      await refreshAdminState();
    } catch (error) {
      showMessage(adminMessage, error.message, false);
    }
  });

  document.getElementById("activity-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const formData = new FormData(form);
    try {
      await requestJson("/admin/activities", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: formData.get("name"),
          description: formData.get("description"),
          schedule: formData.get("schedule"),
          max_participants: Number(formData.get("max_participants")),
        }),
      });
      form.reset();
      showMessage(adminMessage, "Activity created", true);
      await fetchActivities();
    } catch (error) {
      showMessage(adminMessage, error.message, false);
    }
  });

  signupForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const email = document.getElementById("email").value;
    const activity = activitySelect.value;
    try {
      const result = await requestJson(
        `/activities/${encodeURIComponent(activity)}/signup?email=${encodeURIComponent(email)}`,
        { method: "POST" }
      );
      showMessage(messageDiv, result.message, true);
      signupForm.reset();
      await fetchActivities();
    } catch (error) {
      showMessage(messageDiv, error.message, false);
    }
  });

  refreshAdminState();
});