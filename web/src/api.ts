export interface FieldSample {
  station_id: string;
  latitude_deg: number;
  longitude_deg: number;
  field_strength_dbuv_m: number;
  expected_receiver_dbm: number;
  expected_s_meter: string;
  receiver_reference: string;
}

export class FieldStrengthApi {
  constructor(readonly baseUrl: string) {}

  tileUrl(stationId: string, minimumDbuvM = 5): string {
    const id = encodeURIComponent(stationId);
    return `${this.baseUrl}/v1/coverage/${id}/tiles/{z}/{x}/{y}.png` +
      `?minimum_field_strength_dbuv_m=${minimumDbuvM}`;
  }

  async sample(stationId: string, latitudeDeg: number, longitudeDeg: number, signal?: AbortSignal): Promise<FieldSample> {
    const query = new URLSearchParams({
      latitude_deg: String(latitudeDeg),
      longitude_deg: String(longitudeDeg),
    });
    const response = await fetch(
      `${this.baseUrl}/v1/coverage/${encodeURIComponent(stationId)}/sample?${query}`,
      { signal },
    );
    if (!response.ok) throw new Error(`Field sample failed with HTTP ${response.status}`);
    return await response.json() as FieldSample;
  }
}
