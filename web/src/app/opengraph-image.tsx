import { ImageResponse } from "next/og";

export const alt = "Pricewise — AI Shopping Agent with Selective Human-in-the-Loop";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default async function OpengraphImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          background: "#f7f4f0",
          display: "flex",
          flexDirection: "column",
          padding: "80px",
          position: "relative",
        }}
      >
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

        <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
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
              fontWeight: 700,
              color: "#2c2825",
              letterSpacing: -0.5,
            }}
          >
            Pricewise
          </div>
        </div>

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
              fontSize: 92,
              fontWeight: 800,
              color: "#2c2825",
              letterSpacing: -2,
              lineHeight: 1.05,
            }}
          >
            AI Shopping Agent
          </div>
          <div
            style={{
              fontSize: 36,
              fontWeight: 400,
              color: "#6b6560",
              marginTop: 16,
              lineHeight: 1.3,
            }}
          >
            with Selective Human-in-the-Loop
          </div>
        </div>

        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
          }}
        >
          <div
            style={{
              fontSize: 22,
              color: "#a39e98",
              fontFamily: "monospace",
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
    { ...size },
  );
}
