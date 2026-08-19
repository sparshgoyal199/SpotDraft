import { api, getToken, setToken } from "./api.js";

if (getToken()) {
  window.location.replace("/dashboard");
}

const form = document.getElementById("auth-form");
const nameField = document.getElementById("name-field");
const errorEl = document.getElementById("error");
const submitBtn = document.getElementById("submit-btn");
const titleEl = document.getElementById("form-title");
const copyEl = document.getElementById("form-copy");
const switchCopy = document.getElementById("switch-copy");
const switchLink = document.getElementById("switch-link");

let mode = "login";

function setMode(next) {
  mode = next;
  const signup = mode === "signup";
  nameField.classList.toggle("hidden", !signup);
  titleEl.textContent = signup ? "Create your workspace" : "Welcome back";
  copyEl.textContent = signup ? "Name, email, and a password. That’s it." : "Sign in to your library.";
  submitBtn.textContent = signup ? "Create account" : "Sign in";
  switchCopy.textContent = signup ? "Already registered?" : "Need an account?";
  switchLink.textContent = signup ? "Sign in" : "Create one";
  document.getElementById("password").autocomplete = signup ? "new-password" : "current-password";
}

switchLink.addEventListener("click", (event) => {
  event.preventDefault();
  setMode(mode === "login" ? "signup" : "login");
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  errorEl.textContent = "";
  submitBtn.disabled = true;
  const payload = {
    email: form.email.value.trim(),
    password: form.password.value,
  };
  try {
    if (mode === "signup") {
      payload.name = form.name.value.trim();
      if (!payload.name) throw new Error("Name is required");
      await api.signup(payload);
    }
    const token = await api.login({ email: payload.email, password: payload.password });
    setToken(token.access_token);
    window.location.replace("/dashboard");
  } catch (err) {
    errorEl.textContent = err.message;
  } finally {
    submitBtn.disabled = false;
  }
});
