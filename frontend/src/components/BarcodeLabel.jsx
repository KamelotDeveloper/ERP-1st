import api from "../services/api";

/**
 * BarcodeLabel — renders a barcode image + product name + price.
 *
 * Props:
 *   value      — the SKU code to encode (string)
 *   name       — product/material name (string)
 *   price      — price to display (number, optional)
 *   showPrice  — whether to show price (boolean, default true)
 *   size       — "small" | "medium" | "large" (default "small")
 */
export default function BarcodeLabel({
  value,
  name,
  price,
  showPrice = true,
  size = "small",
}) {
  if (!value) {
    return <span style={{ color: "#999" }}>-</span>;
  }

  const baseURL = api.defaults.baseURL || "";
  const barcodeUrl = `${baseURL}/barcodes/${encodeURIComponent(value)}.png`;

  const dimensions = {
    small: { width: 140, fontSize: "0.7rem" },
    medium: { width: 200, fontSize: "0.8rem" },
    large: { width: 300, fontSize: "1rem" },
  };

  const dim = dimensions[size] || dimensions.small;

  return (
    <div
      style={{
        display: "inline-flex",
        flexDirection: "column",
        alignItems: "center",
        gap: "2px",
      }}
    >
      <img
        src={barcodeUrl}
        alt={`Barcode ${value}`}
        style={{ width: dim.width, height: "auto" }}
        onError={(e) => {
          e.target.style.display = "none";
        }}
      />
      {name && (
        <span
          style={{
            fontSize: dim.fontSize,
            color: "#333",
            textAlign: "center",
            maxWidth: dim.width + 40,
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
          }}
        >
          {name}
        </span>
      )}
      {showPrice && price != null && (
        <span
          style={{
            fontSize: dim.fontSize,
            fontWeight: "bold",
            color: "#22c55e",
          }}
        >
          ${Number(price).toLocaleString()}
        </span>
      )}
    </div>
  );
}
