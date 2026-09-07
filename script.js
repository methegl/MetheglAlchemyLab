(() => {
  const card = document.querySelector("#featured-stream");
  if (!card) return;

  const setText = (selector, value) => {
    const element = card.querySelector(selector);
    if (element && value) element.textContent = value;
  };

  fetch("stream-data.json", { cache: "no-store" })
    .then((response) => {
      if (!response.ok) throw new Error("stream data is unavailable");
      return response.json();
    })
    .then((stream) => {
      if (!stream?.videoId || !stream?.title) return;

      const isLive = stream.kind === "live";
      const url = `https://www.youtube.com/watch?v=${stream.videoId}`;
      const thumbnail = card.querySelector(".stream-thumbnail");
      const image = thumbnail?.querySelector("img");
      const button = card.querySelector(".stream-button");

      card.dataset.streamState = isLive ? "live" : "video";
      card.classList.toggle("is-live", isLive);

      if (thumbnail) {
        thumbnail.href = url;
        thumbnail.setAttribute("aria-label", `${stream.title}をYouTubeで見る`);
      }
      if (image) {
        image.src = stream.thumbnail || `https://i.ytimg.com/vi/${stream.videoId}/maxresdefault.jpg`;
        image.alt = `${stream.title}のサムネイル`;
      }
      if (button) {
        button.href = url;
        button.textContent = isLive ? "配信を見る ↗" : "動画を見る ↗";
      }

      setText("[data-stream-signal]", isLive ? "ON AIR" : "NEW VIDEO");
      setText("[data-stream-type]", isLive ? "LIVE NOW ／ 配信中" : "LATEST VIDEO ／ 最新動画");
      setText("[data-stream-date]", isLive ? "ただいま配信中" : "最新の通常動画");
      setText("[data-stream-title]", stream.title);
      setText(
        "[data-stream-description]",
        isLive
          ? "ギネス・ノワールが現在配信中です。YouTubeで工房の観測に参加できます。"
          : "ギネス・ノワールの最新の通常動画です。YouTubeで新しい観測記録を確認できます。"
      );
      setText("[data-stream-tag]", isLive ? "Live Now" : "New Video");
    })
    .catch((error) => {
      console.warn("ストリーム情報を読み込めませんでした。", error);
    });
})();
