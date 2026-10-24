import type { AssetResolver, ResolvedAsset } from "./types.js";
import { GenerationRendererError } from "./validation.js";

const LOCAL_FIXTURE_PATH = /^\/generation-fixtures\/[a-z0-9][a-z0-9/_-]*\.(?:png|svg|webp)$/;

export class SyntheticAssetResolver implements AssetResolver {
  readonly #assets: ReadonlyMap<string, ResolvedAsset>;

  constructor(assets: Iterable<ResolvedAsset>) {
    const validated = new Map<string, ResolvedAsset>();
    for (const asset of assets) {
      if (
        !LOCAL_FIXTURE_PATH.test(asset.src) ||
        !Number.isInteger(asset.width) ||
        asset.width <= 0 ||
        !Number.isInteger(asset.height) ||
        asset.height <= 0 ||
        validated.has(asset.assetRef)
      ) {
        throw new GenerationRendererError("GENERATION_RENDERER_ASSET_NOT_AUTHORIZED");
      }
      validated.set(asset.assetRef, Object.freeze({ ...asset }));
    }
    this.#assets = validated;
  }

  resolve(assetRef: string): ResolvedAsset | null {
    return this.#assets.get(assetRef) ?? null;
  }
}
