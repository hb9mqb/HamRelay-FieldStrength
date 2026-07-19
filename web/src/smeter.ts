import { Cartesian2, Cartographic, ScreenSpaceEventHandler, ScreenSpaceEventType, Viewer } from "cesium";
import { FieldSample, FieldStrengthApi } from "./api.js";
import type { CoverageOverlayController } from "./overlay.js";

export interface HoverOptions {
  debounceMs?: number;
  render: (sample: FieldSample | null, screen: { x: number; y: number }) => void;
}

export class SMeterHover {
  private readonly events: ScreenSpaceEventHandler;
  private timer?: ReturnType<typeof setTimeout>;
  private request?: AbortController;

  constructor(
    private readonly viewer: Viewer,
    private readonly api: FieldStrengthApi,
    private readonly visibleStationIds: () => string[],
    private readonly options: HoverOptions,
  ) {
    this.events = new ScreenSpaceEventHandler(viewer.scene.canvas);
    this.events.setInputAction((movement: { endPosition: Cartesian2 }) => {
      if (this.timer) clearTimeout(this.timer);
      this.timer = setTimeout(() => void this.sample(movement.endPosition), options.debounceMs ?? 120);
    }, ScreenSpaceEventType.MOUSE_MOVE);
  }

  destroy(): void {
    if (this.timer) clearTimeout(this.timer);
    this.request?.abort();
    this.events.destroy();
  }

  private async sample(screen: Cartesian2): Promise<void> {
    const cartesian = this.viewer.camera.pickEllipsoid(screen, this.viewer.scene.globe.ellipsoid);
    if (!cartesian) return this.options.render(null, screen);
    const point = Cartographic.fromCartesian(cartesian);
    const latitude = point.latitude * 180 / Math.PI;
    const longitude = point.longitude * 180 / Math.PI;
    this.request?.abort();
    this.request = new AbortController();
    const samples = await Promise.allSettled(
      this.visibleStationIds().map(id => this.api.sample(id, latitude, longitude, this.request?.signal)),
    );
    const available = samples
      .filter((item): item is PromiseFulfilledResult<FieldSample> => item.status === "fulfilled")
      .map(item => item.value)
      .sort((a, b) => b.field_strength_dbuv_m - a.field_strength_dbuv_m);
    this.options.render(available[0] ?? null, screen);
  }
}

export function createLegend(): HTMLElement {
  const element = document.createElement("div");
  element.className = "field-strength-legend";
  element.innerHTML = `
    <strong>Field strength</strong><span>dBµV/m</span>
    <div aria-label="Field-strength color scale" style="height:12px;border-radius:6px;background:linear-gradient(90deg,#7837d2,#2d5ae6,#00cde1,#23c35f,#fad72d,#ff871e,#e62d23)"></div>
    <div style="display:flex;justify-content:space-between"><span>0</span><span>20</span><span>40</span><span>60</span><span>80</span><span>100</span></div>
    <small>S readings are receiver-reference estimates; dBµV/m is the primary quantity.</small>
    <small style="display:block;margin-top:6px;opacity:.72">Designed with ♥ by Beat W. Meier, HB9MQB</small>`;
  return element;
}

export function createOverlayControls(controller: CoverageOverlayController): HTMLElement {
  const element = document.createElement("section");
  element.className = "field-strength-controls";
  element.innerHTML = `
    <label>Opacity <output data-opacity>70%</output>
      <input data-opacity-slider type="range" min="0" max="100" value="70" step="1">
    </label>
    <label>Minimum field strength <output data-threshold>5 dBµV/m</output>
      <input data-threshold-slider type="range" min="0" max="50" value="5" step="1">
    </label>
    <small style="display:block;margin-top:8px;opacity:.72">Designed with ♥ by Beat W. Meier, HB9MQB</small>`;
  const opacity = element.querySelector<HTMLInputElement>("[data-opacity-slider]")!;
  const opacityOutput = element.querySelector<HTMLOutputElement>("[data-opacity]")!;
  opacity.addEventListener("input", () => {
    controller.setOpacity(Number(opacity.value) / 100);
    opacityOutput.value = `${opacity.value}%`;
  });
  const threshold = element.querySelector<HTMLInputElement>("[data-threshold-slider]")!;
  const thresholdOutput = element.querySelector<HTMLOutputElement>("[data-threshold]")!;
  threshold.addEventListener("input", () => {
    controller.setMinimumFieldStrength(Number(threshold.value));
    thresholdOutput.value = `${threshold.value} dBµV/m`;
  });
  return element;
}
