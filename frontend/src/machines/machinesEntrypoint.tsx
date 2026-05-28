import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { MachineProfileApp } from "./MachineProfileApp";
import { MachinesOverviewApp } from "./MachinesOverviewApp";

const MACHINES_ROOT_ID = "maintenance-machines-root";
const MACHINE_PROFILE_ROOT_ID = "maintenance-machine-profile-root";

/**
 * Mount the matching machines React island for the current route.
 */
function bootstrapMachinesIsland(): void {
  const overviewRoot = document.getElementById(MACHINES_ROOT_ID);
  const profileRoot = document.getElementById(MACHINE_PROFILE_ROOT_ID);

  if (overviewRoot) {
    createRoot(overviewRoot).render(
      <StrictMode>
        <MachinesOverviewApp />
      </StrictMode>
    );
    return;
  }

  if (profileRoot) {
    createRoot(profileRoot).render(
      <StrictMode>
        <MachineProfileApp />
      </StrictMode>
    );
  }
}

bootstrapMachinesIsland();
