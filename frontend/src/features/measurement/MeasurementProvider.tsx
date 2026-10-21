import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import type { Extraction, Measurements } from "../../types/studio";
type State = {
  file: File | undefined;
  setFile: (file: File | undefined) => void;
  height: number;
  setHeight: (value: number) => void;
  extraction: Extraction | undefined;
  setExtraction: (value: Extraction | undefined) => void;
  measurements: Measurements | undefined;
  setMeasurements: (value: Measurements | undefined) => void;
  edited: boolean;
  setEdited: (value: boolean) => void;
};
const Context = createContext<State | null>(null);
export function MeasurementProvider({ children }: { children: ReactNode }) {
  const [file, rawSetFile] = useState<File>();
  const [height, setHeight] = useState(172);
  const [extraction, setExtraction] = useState<Extraction>();
  const [measurements, setMeasurements] = useState<Measurements>();
  const [edited, setEdited] = useState(false);
  const setFile = (value: File | undefined) => {
    rawSetFile(value);
    setExtraction(undefined);
    setMeasurements(undefined);
    setEdited(false);
  };
  useEffect(() => {
    const clear = () => {
      setFile(undefined);
      setHeight(172);
    };
    window.addEventListener("formfit:clear-private", clear);
    return () => window.removeEventListener("formfit:clear-private", clear);
  }, []);
  return (
    <Context.Provider
      value={{
        file,
        setFile,
        height,
        setHeight,
        extraction,
        setExtraction,
        measurements,
        setMeasurements,
        edited,
        setEdited,
      }}
    >
      {children}
    </Context.Provider>
  );
}
export function useMeasurement() {
  const state = useContext(Context);
  if (!state) throw new Error("MeasurementProvider is missing");
  return state;
}
