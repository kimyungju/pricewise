import { ImageResponse } from "next/og";

export const alt = "Pricewise — AI Shopping Agent with Selective Human-in-the-Loop";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

const SUBSET =
  "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789 .,—·-':/";

async function loadGoogleFont(
  family: string,
  weight: number,
  italic = false,
): Promise<ArrayBuffer> {
  const fam = family.replace(/ /g, "+");
  const variant = italic ? `${weight}italic` : `${weight}`;
  const url = `https://fonts.googleapis.com/css?family=${fam}:${variant}&text=${encodeURIComponent(SUBSET)}`;
  const css = await fetch(url, {
    headers: {
      "User-Agent":
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_6) AppleWebKit/603.3.8 (KHTML, like Gecko) Version/10.1.2 Safari/603.3.8",
    },
  }).then((r) => r.text());
  const match = css.match(/src:\s*url\((.+?)\)/);
  if (!match) throw new Error(`Failed to load font: ${family} ${variant}`);
  return fetch(match[1]).then((r) => r.arrayBuffer());
}

export default async function OpengraphImage() {
  const [playfair, dmSans] = await Promise.all([
    loadGoogleFont("Playfair Display", 800),
    loadGoogleFont("DM Sans", 500),
  ]);

  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          background:
            "linear-gradient(135deg, #faf6f0 0%, #f3ede5 60%, #ece4d9 100%)",
          display: "flex",
          flexDirection: "column",
          padding: "80px",
          position: "relative",
          fontFamily: "DM Sans, sans-serif",
        }}
      >
        {/* Vertical accent bar */}
        <div
          style={{
            position: "absolute",
            left: 0,
            top: 0,
            bottom: 0,
            width: "16px",
            background: "#b86e2f",
          }}
        />

        {/* TOP: brand */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "16px",
          }}
        >
          <div
            style={{
              width: 14,
              height: 14,
              borderRadius: 7,
              background: "#b86e2f",
            }}
          />
          <div
            style={{
              fontSize: 32,
              fontWeight: 800,
              color: "#2c2825",
              letterSpacing: -0.5,
              fontFamily: "Playfair Display, serif",
            }}
          >
            Pricewise
          </div>
        </div>

        {/* HERO */}
        <div
          style={{
            flex: 1,
            display: "flex",
            flexDirection: "column",
            justifyContent: "center",
          }}
        >
          <div
            style={{
              fontSize: 17,
              fontWeight: 700,
              color: "#b86e2f",
              letterSpacing: 4,
              textTransform: "uppercase",
            }}
          >
            AI Shopping Agent
          </div>
          <div
            style={{
              fontSize: 124,
              fontWeight: 800,
              color: "#2c2825",
              letterSpacing: -3.5,
              lineHeight: 0.95,
              marginTop: 18,
              fontFamily: "Playfair Display, serif",
            }}
          >
            Selective trust.
          </div>
          <div
            style={{
              width: 80,
              height: 4,
              background: "#b86e2f",
              marginTop: 36,
            }}
          />
          <div
            style={{
              fontSize: 26,
              fontWeight: 400,
              color: "#6b6560",
              marginTop: 24,
              maxWidth: 880,
              lineHeight: 1.45,
            }}
          >
            10 specialized tools in one conversation. Every external API call gates on explicit user approval.
          </div>
        </div>

        {/* FOOTER */}
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
          }}
        >
          <div
            style={{
              fontSize: 20,
              color: "#a39e98",
              fontFamily: "monospace",
              letterSpacing: 0.5,
            }}
          >
            LangGraph · OpenAI · FastAPI · Next.js
          </div>
          <div
            style={{
              fontSize: 18,
              color: "#a39e98",
              fontFamily: "monospace",
            }}
          >
            kimyungju.com
          </div>
        </div>
      </div>
    ),
    {
      ...size,
      fonts: [
        {
          name: "Playfair Display",
          data: playfair,
          weight: 800,
          style: "normal",
        },
        {
          name: "DM Sans",
          data: dmSans,
          weight: 500,
          style: "normal",
        },
      ],
    },
  );
}
