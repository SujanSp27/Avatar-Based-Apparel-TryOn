import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import type { Extraction, Measurements, Metric } from "../../types/studio";
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
  reviewedMetrics: Metric[];
  correctMeasurement: (key: Metric, value: number) => void;
};
const Context = createContext<State | null>(null);
export function MeasurementProvider({ children }: { children: ReactNode }) {
  const [file, rawSetFile] = useState<File>();
  const [height, setHeight] = useState(172);
  const [extraction, rawSetExtraction] = useState<Extraction>();
  const [measurements, setMeasurements] = useState<Measurements>();
  const [edited, setEdited] = useState(false);
  const [reviewedMetrics, setReviewedMetrics] = useState<Metric[]>([]);
  const setExtraction = (value: Extraction | undefined) => {
    rawSetExtraction(value);
    setReviewedMetrics([]);
  };
  const correctMeasurement = (key: Metric, value: number) => {
    setMeasurements((previous) => ({
      shoulder_width: 0,
      chest_circumference: 0,
      waist_circumference: 0,
      hip_circumference: 0,
      thigh_circumference: 0,
      inseam_length: 0,
      ...previous,
      [key]: value,
    }));
    setReviewedMetrics((previous) => [...new Set([...previous, key])]);
    setEdited(true);
  };
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
        reviewedMetrics,
        correctMeasurement,
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
