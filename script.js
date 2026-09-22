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
      const isArchive = stream.kind === "archive";

      const url = `https://www.youtube.com/watch?v=${stream.videoId}`;

      const thumbnail = card.querySelector(".stream-thumbnail");
      const image = thumbnail?.querySelector("img");
      const button = card.querySelector(".stream-button");

      /* ------------------------------
         カード状態
      ------------------------------ */

      card.dataset.streamState = stream.kind || "video";
      card.classList.toggle("is-live", isLive);
      card.classList.toggle("is-archive", isArchive);

      /* ------------------------------
         URL / サムネイル
      ------------------------------ */

      if (thumbnail) {
        thumbnail.href = url;
        thumbnail.setAttribute(
          "aria-label",
          `${stream.title}をYouTubeで見る`
        );
      }

      if (image) {
        image.src =
          stream.thumbnail ||
          `https://i.ytimg.com/vi/${stream.videoId}/maxresdefault.jpg`;

        image.alt = `${stream.title}のサムネイル`;
      }

      if (button) {
        button.href = url;

        if (isLive) {
          button.textContent = "配信を見る ↗";
        } else if (isArchive) {
          button.textContent = "アーカイブを見る ↗";
        } else {
          button.textContent = "動画を見る ↗";
        }
      }

      /* ------------------------------
         表示テキスト
      ------------------------------ */

      if (isLive) {
        setText("[data-stream-signal]", "ON AIR");
        setText("[data-stream-type]", "LIVE NOW ／ 配信中");
        setText("[data-stream-date]", "ただいま配信中");

        setText(
          "[data-stream-description]",
          "ギネス・ノワールが現在配信中です。YouTubeで工房の観測に参加できます。"
        );

        setText("[data-stream-tag]", "Live Now");

      } else if (isArchive) {
        setText("[data-stream-signal]", "NEW ARCHIVE");
        setText(
          "[data-stream-type]",
          "LATEST ARCHIVE ／ 最新アーカイブ"
        );
        setText(
          "[data-stream-date]",
          "最新の配信アーカイブ"
        );

        setText(
          "[data-stream-description]",
          "ギネス・ノワールの最新の配信アーカイブです。工房で行われた実験と観測の記録を確認できます。"
        );

        setText("[data-stream-tag]", "Archive");

      } else {
        setText("[data-stream-signal]", "NEW VIDEO");
        setText(
          "[data-stream-type]",
          "LATEST VIDEO ／ 最新動画"
        );
        setText(
          "[data-stream-date]",
          "最新の通常動画"
        );

        setText(
          "[data-stream-description]",
          "ギネス・ノワールの最新の通常動画です。YouTubeで新しい観測記録を確認できます。"
        );

        setText("[data-stream-tag]", "New Video");
      }

      setText("[data-stream-title]", stream.title);
    })
    .catch((error) => {
      console.warn(
        "ストリーム情報を読み込めませんでした。",
        error
      );
    });
})();