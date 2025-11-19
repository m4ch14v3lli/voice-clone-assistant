let mediaRecorder;
let chunks = [];

document.getElementById("recordBtn").onclick = async () => {
  if (!mediaRecorder || mediaRecorder.state === "inactive") {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    mediaRecorder = new MediaRecorder(stream);

    mediaRecorder.ondataavailable = e => chunks.push(e.data);
    mediaRecorder.onstop = sendAudio;

    mediaRecorder.start();
    console.log("Recording...");
  } else {
    mediaRecorder.stop();
  }
};

async function sendAudio() {
  const blob = new Blob(chunks, { type: "audio/wav" });
  const form = new FormData();
  form.append("audio", blob, "audio.wav");

  const res = await fetch("http://localhost:8000/assistant?voice_id=your-id-here", {
    method: "POST",
    body: form
  });

  const data = await res.json();
  const audioBytes = new Uint8Array(
    data.audio.match(/.{1,2}/g).map(byte => parseInt(byte, 16))
  );

  const audioBlob = new Blob([audioBytes], { type: "audio/wav" });
  document.getElementById("responseAudio").src = URL.createObjectURL(audioBlob);
}
