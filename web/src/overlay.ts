import { GeographicTilingScheme, ImageryLayer, UrlTemplateImageryProvider, Viewer } from "cesium";
import { FieldStrengthApi } from "./api.js";

export interface OverlayOptions {
  opacity?: number;
  minimumFieldStrengthDbuvM?: number;
}

export class CoverageOverlayController {
  private readonly layers = new Map<string, ImageryLayer>();
  private opacity: number;
  private threshold: number;

  constructor(
    private readonly viewer: Viewer,
    private readonly api: FieldStrengthApi,
    options: OverlayOptions = {},
  ) {
    this.opacity = options.opacity ?? 0.7;
    this.threshold = options.minimumFieldStrengthDbuvM ?? 5;
  }

  show(stationId: string): void {
    if (this.layers.has(stationId)) return;
    const provider = new UrlTemplateImageryProvider({
      url: this.api.tileUrl(stationId, this.threshold),
      tilingScheme: new GeographicTilingScheme(),
      minimumLevel: 0,
      maximumLevel: 18,
      hasAlphaChannel: true,
    });
    const layer = this.viewer.imageryLayers.addImageryProvider(provider);
    layer.alpha = this.opacity;
    this.layers.set(stationId, layer);
    // Deliberately do not fly, zoom, or mutate the camera.
    this.viewer.scene.requestRender();
  }

  hide(stationId: string): void {
    const layer = this.layers.get(stationId);
    if (layer) this.viewer.imageryLayers.remove(layer, true);
    this.layers.delete(stationId);
  }

  setVisibleStations(stationIds: Iterable<string>): void {
    const wanted = new Set(stationIds);
    for (const id of this.layers.keys()) if (!wanted.has(id)) this.hide(id);
    for (const id of wanted) this.show(id);
  }

  setOpacity(opacity: number): void {
    this.opacity = Math.max(0, Math.min(1, opacity));
    for (const layer of this.layers.values()) layer.alpha = this.opacity;
    this.viewer.scene.requestRender();
  }

  setMinimumFieldStrength(dbuvM: number): void {
    this.threshold = Math.max(0, Math.min(50, dbuvM));
    const ids = [...this.layers.keys()];
    for (const id of ids) this.hide(id);
    for (const id of ids) this.show(id);
  }
}
