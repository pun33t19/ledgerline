import { Route, Routes } from "react-router";
import { Layout } from "./components/Layout";
import { CoveragePage } from "./pages/CoveragePage";
import { LabPage } from "./pages/LabPage";
import { NotFound } from "./pages/NotFound";
import { RunPage } from "./pages/RunPage";

export function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<LabPage />} />
        <Route path="runs/:runId" element={<RunPage />} />
        <Route path="coverage" element={<CoveragePage />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
