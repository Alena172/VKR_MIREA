import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import { PendingReviewProvider } from "./context/PendingReviewContext";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <BrowserRouter>
      <PendingReviewProvider>
        <App />
      </PendingReviewProvider>
    </BrowserRouter>
  </React.StrictMode>
);
