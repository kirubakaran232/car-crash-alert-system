function updateStatus() {
  fetch("/status")
    .then((response) => response.json())
    .then((data) => {
      document.getElementById("vibrationValue").innerText = data.vibration;
      document.getElementById("alertNeeded").innerText = data.alert_needed
        ? "Yes"
        : "No";
      document.getElementById("alertSent").innerText = data.alert_sent
        ? "Yes"
        : "No";
      document.getElementById("confirmationTimeLeft").innerText =
        data.confirmation_time_left;
    })
    .catch((error) => console.log("Error fetching status:", error));
}

// Call every second
setInterval(updateStatus, 1000);
