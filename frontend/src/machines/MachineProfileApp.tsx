import {
  useEffect,
  useLayoutEffect,
  useState,
  type ReactNode
} from "react";

import { markIslandMounted } from "../app/islandMount";
import { loadMachineProfile } from "./machineApi";
import { MachineProfileView } from "./components/MachineProfileView";
import type { MachineProfile } from "./machineTypes";
import { machineErrorMessage } from "./machineUtils";

const MACHINE_PROFILE_ISLAND = {
  fallbackSelector: "[data-react-machine-profile-fallback]",
  mountedFlag: "maintenanceMachinesReactMounted",
  mountEvent: "maintenance-machines-react-mounted"
};

/**
 * Read the machine id from the legacy profile fallback.
 */
function readMachineId(): number | null {
  const reactRoot = document.getElementById("maintenance-machine-profile-root");
  const fallbackRoot = document.querySelector<HTMLElement>("[data-machine-profile-page]");
  const rawValue = reactRoot?.dataset.machineId || fallbackRoot?.dataset.machineId || "";
  const machineId = Number(rawValue);
  return Number.isFinite(machineId) && machineId > 0 ? machineId : null;
}

/**
 * Render the React machine profile island.
 */
export function MachineProfileApp(): ReactNode {
  const [message, setMessage] = useState("Maschinenprofil wird geladen...");
  const [profile, setProfile] = useState<MachineProfile | null>(null);

  useLayoutEffect(() => {
    markIslandMounted(MACHINE_PROFILE_ISLAND);
  }, []);

  useEffect(() => {
    const machineId = readMachineId();
    if (!machineId) {
      setMessage("Maschinen-ID fehlt.");
      return;
    }

    loadMachineProfile(machineId)
      .then((loadedProfile) => {
        setProfile(loadedProfile);
        setMessage("Maschinenprofil bereit.");
      })
      .catch((error: unknown) => {
        setMessage(machineErrorMessage(error));
      });
  }, []);

  return <MachineProfileView message={message} profile={profile} />;
}
