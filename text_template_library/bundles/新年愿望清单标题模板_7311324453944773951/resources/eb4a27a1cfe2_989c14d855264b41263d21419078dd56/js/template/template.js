'use strict';

Object.defineProperty(exports, '__esModule', { value: true });

class TimeRange {
  constructor(startTime = 0, duration = 0) {
    this.startTime = startTime;
    this.duration = duration;
  }

  get endTime() {
    return this.startTime + this.duration;
  }

  set endTime(endTime) {
    if (this.endTime != endTime) {
      this.duration = endTime - this.startTime;
    }
  }

}

var Amaz$1 = effect.Amaz;
var Color = Amaz$1.Color;
var AmazUtils;

(function (AmazUtils) {
  AmazUtils.initAmazEntity = function (entity) {
    // Transform
    Object.defineProperty(entity, 'transform', {
      get() {
        let trans = this.getComponent('Transform');

        if (!trans) {
          trans = this.addComponent('Transform');
        }

        return trans;
      },

      set(value) {
        AmazUtils.setEntityTransform(this, value);
      }

    }); // camera

    Object.defineProperty(entity, 'camera', {
      get() {
        let trans = this.getComponent('Camera');

        if (!trans) {
          trans = this.addComponent('Camera');
        }

        return trans;
      }

    });
  };

  AmazUtils.setEntityTransform = function (entity, options) {
    let trans = entity.getComponent('Transform');

    if (!trans) {
      trans = entity.addComponent('Transform');
    }

    trans.localPosition = options.position;
    trans.localEulerAngle = options.rotation;
    trans.localScale = options.scale;
  };

  AmazUtils.createEntity = function (name, scene) {
    const ent = scene.createEntity(name);
    AmazUtils.initAmazEntity(ent);
    return ent;
  };

  AmazUtils.addChildEntity = function (parent, child) {
    child.transform.parent = parent.transform;
    parent.transform.addTransform(child.transform);
  };

  AmazUtils.removeChildEntity = function (parent, child) {
    parent.transform.removeTransform(child.transform);
  };

  AmazUtils.getRenderers = function (rootEntity) {
    const renderers = new Amaz$1.Vector();

    if (null !== rootEntity) {
      const renderersTmp = rootEntity.getComponentsRecursive('Renderer');

      if (!renderersTmp.empty()) {
        const size = renderersTmp.size();

        for (let i = 0; i < size; i++) {
          renderers.pushBack(renderersTmp.get(i));
        }
      }
    }

    return renderers;
  };

  AmazUtils.CastJsonArray4fToAmazVector4f = function (jsonArray) {
    let result = null;

    if (jsonArray instanceof Array && jsonArray.length === 4) {
      result = new Amaz$1.Vector4f(jsonArray[0], jsonArray[1], jsonArray[2], jsonArray[3]);
    }

    return result;
  };

  AmazUtils.CastJsonArray3fToAmazVector3f = function (jsonArray) {
    let result = null;

    if (jsonArray instanceof Array && jsonArray.length === 3) {
      result = new Amaz$1.Vector3f(jsonArray[0], jsonArray[1], jsonArray[2]);
    }

    return result;
  };

  AmazUtils.CastJsonArray2fToAmazVector2f = function (jsonArray) {
    let result = null;

    if (jsonArray instanceof Array && jsonArray.length === 2) {
      result = new Amaz$1.Vector2f(jsonArray[0], jsonArray[1]);
    }

    return result;
  };

  AmazUtils.CastJsonArrayToAmazVector = function (jsonArray) {
    const result = new Amaz$1.Vector();

    if (jsonArray instanceof Array) {
      for (let i = 0; i < jsonArray.length; i++) {
        const jsonValue = jsonArray[i];
        result.pushBack(jsonValue);
      }
    }

    return result;
  };

  AmazUtils.CastJsonArray4fToColor = function (jsonArray) {
    let result = null;

    if (jsonArray instanceof Array && jsonArray.length === 4) {
      result = new Color(jsonArray[0], jsonArray[1], jsonArray[2], jsonArray[3]);
    }

    return result;
  };

  AmazUtils.CreateQuadMesh = function () {
    const fv = new Amaz$1.FloatVector();
    const ary = new Amaz$1.UInt16Vector();
    fv.pushBack(-1.0);
    fv.pushBack(-1.0);
    fv.pushBack(0.0);
    fv.pushBack(0.0);
    fv.pushBack(0.0);
    fv.pushBack(1.0);
    fv.pushBack(-1.0);
    fv.pushBack(0.0);
    fv.pushBack(1.0);
    fv.pushBack(0.0);
    fv.pushBack(1.0);
    fv.pushBack(1.0);
    fv.pushBack(0.0);
    fv.pushBack(1.0);
    fv.pushBack(1.0);
    fv.pushBack(-1.0);
    fv.pushBack(1.0);
    fv.pushBack(0.0);
    fv.pushBack(0.0);
    fv.pushBack(1.0);
    const quadMesh = new Amaz$1.Mesh();
    quadMesh.clearAfterUpload = true;
    quadMesh.vertices = fv;
    const posDesc = new Amaz$1.VertexAttribDesc();
    posDesc.semantic = Amaz$1.VertexAttribType.POSITION;
    const uvDesc = new Amaz$1.VertexAttribDesc();
    uvDesc.semantic = Amaz$1.VertexAttribType.TEXCOORD0;
    const vads = new Amaz$1.Vector();
    vads.pushBack(posDesc);
    vads.pushBack(uvDesc);
    quadMesh.vertexAttribs = vads;
    const aabb = new Amaz$1.AABB();
    aabb.min_x = -1.0;
    aabb.min_y = -1.0;
    aabb.min_z = 0.0;
    aabb.max_x = 1.0;
    aabb.max_y = 1.0;
    aabb.max_z = 0.0;
    quadMesh.boundingBox = aabb;
    const subMesh = new Amaz$1.SubMesh();
    ary.pushBack(0);
    ary.pushBack(1);
    ary.pushBack(2);
    ary.pushBack(3);
    subMesh.indices16 = ary;
    subMesh.primitive = Amaz$1.Primitive.TRIANGLE_FAN;
    subMesh.boundingBox = aabb;
    quadMesh.addSubMesh(subMesh);
    return quadMesh;
  };
})(AmazUtils || (AmazUtils = {}));

var AmazUtils$1 = AmazUtils;

var TemplateEventType;

(function (TemplateEventType) {
  TemplateEventType[TemplateEventType["layerOperation"] = 10100] = "layerOperation";
})(TemplateEventType || (TemplateEventType = {}));

class AmazFileUtils {
  /**
   * desc
   * @date 2023-06-08
   * @param {buf}: {buf: ArrayBuffer} parm1
   * @return { string}
   */
  static utf8ArrayToStr(array) {
    let out = '';
    const len = array.length;
    let i = 0;
    let char2 = null;
    let char3 = null;

    while (i < len) {
      const c = array[i++];

      switch (c >> 4) {
        case 0:
        case 1:
        case 2:
        case 3:
        case 4:
        case 5:
        case 6:
        case 7:
          // 0xxxxxxx
          out += String.fromCharCode(c);
          break;

        case 12:
        case 13:
          // 110x xxxx   10xx xxxx
          char2 = array[i++];
          out += String.fromCharCode((c & 0x1f) << 6 | char2 & 0x3f);
          break;

        case 14:
          // 1110 xxxx  10xx xxxx  10xx xxxx
          char2 = array[i++];
          char3 = array[i++];
          out += String.fromCharCode((c & 0x0f) << 12 | (char2 & 0x3f) << 6 | (char3 & 0x3f) << 0);
          break;
      }
    }

    return out;
  }

  static ab2str(buf) {
    const array = new Uint8Array(buf);
    const resultStr = AmazFileUtils.utf8ArrayToStr(array);
    return resultStr; //return String.fromCharCode.apply(null, array);this function just for ascii
  }

  static readFileContent(filePath) {
    try {
      const stateFile = fs.statSync(filePath);

      if (stateFile && stateFile.isFile()) {
        const content = fs.readFileSync(filePath); // ByteSec: ignore FILE_OPER

        if (content) {
          return AmazFileUtils.ab2str(content);
        }
      }
    } catch (e) {
      console.error('AMAZINGTEMPLATE', 'read file content error:', e);
    }

    return undefined;
  }

}

var Amaz = effect.Amaz;
const TEMPLATE_TAG = 'AMAZINGTEMPLATE';
const contentDefault = {
  type: 'ScriptTemplate',
  root: {
    name: 'rootWidget',
    preview_time: 1.5,
    duration: 3
  }
};

class TemplatePrivateUtils {
  /**
   * desc
   * @date 2022-07-08
   * @param {path: string} path
   * @returns { Scene}
   */
  static buildGenericScene(path) {
    const scene = new Amaz.Scene(); // asset manager

    const am = new Amaz.AssetManager();
    am.rootDir = path;
    scene.setAssetManager(am); // scene properties

    scene.visible = true;
    scene.name = 'template_scene';
    scene.jsScriptSystems.pushBack('js/main.js'); // add IFRootSystem for shape

    scene.addSystem('IFRootSystem'); // add camera

    TemplatePrivateUtils.addCameraEntityToNativeScene(scene);
    return scene;
  }

  static addCameraEntityToNativeScene(scene) {
    const ent = AmazUtils$1.createEntity('InfoSticker_camera_entity', scene);
    const trans = ent.transform;
    const ca = ent.camera;
    trans.localPosition = new Amaz.Vector3f(0.0, 0.0, 10.0);
    trans.localEulerAngle = new Amaz.Vector3f(0.0, 0.0, 0.0);
    trans.localScale = new Amaz.Vector3f(1.0, 1.0, 1.0);
    ca.type = Amaz.CameraType.ORTHO;
    ca.clearType = Amaz.CameraClearType.DONT;
    ca.fovy = 60.0;
    ca.zNear = 0.1;
    ca.zFar = 1000.0;
    ca.orthoScale = 1.0;
    ca.renderOrder = 1;
    const layerObj = new Amaz.DynamicBitset(1, 1);
    ca.layerVisibleMask = layerObj;
    const rt = new Amaz.SceneOutputRT();
    ca.renderTexture = rt;
  }

}

class Template {
  /**
   * desc
   * @date 2022-07-08
   */
  constructor() {
    this.scenes = [];
    this.m_templateTimeRange = new TimeRange(0, 0);
    this.m_screenSize = new Amaz.Vector2f(0.0, 0.0);
    this.m_resolutionType = 0; // resolution type just for root widget

    this.m_mainJSRef = null;
  }
  /**
   * desc
   * @date 2022-07-08
   * @param {pathPrefix: string} pathPrefix
   * @param { screenWidth: number}
   */


  init(pathPrefix, screenWidth, screenHeight, dependResource = '') {
    // Load scene
    this.scenes.push(TemplatePrivateUtils.buildGenericScene(pathPrefix)); // Read file

    const contentJsonPath = pathPrefix + '/content.json';
    let contentJson = AmazFileUtils.readFileContent(contentJsonPath);

    if (contentJson === undefined) {
      contentJson = JSON.stringify(contentDefault);
    }

    const screenSize = new Amaz.Vector2f(screenWidth, screenHeight);

    if (contentJson != undefined) {
      this.scenes.map(scene => {
        scene.config.set('params', contentJson);

        if (dependResource != null) {
          scene.config.set('depends', dependResource);
        }

        scene.config.set('screenSize', screenSize);
        scene.config.set('resolutionType', this.m_resolutionType);
      });
    }

    this.m_screenSize.x = screenWidth;
    this.m_screenSize.y = screenHeight;
  }
  /**
   * desc
   * @date 2022-07-08
   */


  destroy() {
    // this.scenes.forEach(value => {
    //   value.destroy();
    // });
    this.m_mainJSRef = null;
    this.scenes = [];
  }
  /**
   * desc
   * @date 2022-07-08
   * @param {parameters: string} parameters
   */


  setParameters(parameters) {
    // const vals = JSON.parse(parameters);
    this.scenes.map(scene => {
      const event = new Amaz.Event();
      event.type = TemplateEventType.layerOperation;
      event.args.pushBack('setParameters');
      event.args.pushBack(parameters);
      scene.postEvent(event);
    });
  }

  getMainJSRef() {
    let currentScene = null;
    this.scenes.map(scene => {
      if (scene && scene.name === 'template_scene') {
        currentScene = scene;
      }
    });

    if (currentScene) {
      const jsSystem = currentScene.getSystem('JSScriptSystem');
      const jsScript = jsSystem.getSystemScriptByName('main');

      if (jsScript) {
        this.m_mainJSRef = jsScript.ref;
      } else {
        console.error(TEMPLATE_TAG, 'JSSystem has no main script!');
      }
    } else {
      console.error(TEMPLATE_TAG, 'currentScene is null in getParameters');
    }
  }

  getParameters(parameters) {
    if (null === this.m_mainJSRef) {
      this.getMainJSRef();
    }

    if (this.m_mainJSRef && 'getParameters' in this.m_mainJSRef) {
      return this.m_mainJSRef.getParameters(parameters);
    } else {
      console.error(TEMPLATE_TAG, 'jsMian is null or has no getParameters property!');
    }

    return '';
  }

  setResolutionType(resolutionType) {
    if (resolutionType !== this.m_resolutionType) {
      this.m_resolutionType = resolutionType;
      this.scenes.map(scene => {
        const event = new Amaz.Event();
        event.type = TemplateEventType.layerOperation;
        event.args.pushBack('setResolutionType');
        event.args.pushBack(resolutionType);
        event.args.pushBack(this.m_screenSize.x);
        event.args.pushBack(this.m_screenSize.y);
        scene.postEvent(event);
      });
    }
  }

  onResize(screen_width, screen_heght) {
    if (this.m_screenSize.x !== screen_width || this.m_screenSize.y !== screen_heght) {
      this.m_screenSize.x = screen_width;
      this.m_screenSize.y = screen_heght;
      this.scenes.map(scene => {
        const event = new Amaz.Event();
        event.type = TemplateEventType.layerOperation;
        event.args.pushBack('setScreenSize');
        event.args.pushBack(screen_width);
        event.args.pushBack(screen_heght);
        scene.postEvent(event);
      });
    }
  }
  /**
   * desc
   * @date 2022-07-08
   * @param {startTime: number} startTime
   * @param {endTime: number} endTime
   */


  setTimeRange(startTime, endTime) {
    if (this.m_templateTimeRange.startTime !== startTime || this.m_templateTimeRange.endTime !== endTime) {
      const event = new Amaz.Event();
      event.type = TemplateEventType.layerOperation;
      event.args.pushBack('setTimeRange');
      event.args.pushBack(startTime);
      event.args.pushBack(endTime);
      this.m_templateTimeRange.startTime = startTime;
      this.m_templateTimeRange.endTime = endTime;
      this.scenes.map(scene => {
        scene.postEvent(event);
      });
    }
  }
  /**
   * desc
   * @date 2022-07-08
   */


  getRuntimeScenes() {
    return this.scenes;
  }

  createLayer(layerName, layerParam) {
    const event = new Amaz.Event();
    event.type = TemplateEventType.layerOperation;
    event.args.pushBack('createLayer');
    event.args.pushBack(layerName);
    event.args.pushBack(layerParam);
    event.args.pushBack(this.m_templateTimeRange.startTime);
    event.args.pushBack(this.m_templateTimeRange.endTime);
    event.args.pushBack(this.m_screenSize.x);
    event.args.pushBack(this.m_screenSize.y);
    this.scenes.map(scene => {
      scene.postEvent(event);
    });
  }

  removeLayer(layerName) {
    const event = new Amaz.Event();
    event.type = TemplateEventType.layerOperation;
    event.args.pushBack('removeLayer');
    event.args.pushBack(layerName);
    this.scenes.map(scene => {
      scene.postEvent(event);
    });
  }

}

const template = Template;
 // # sourceMappingURL=index.js.map

exports.Template = Template;
exports.template = template;
//# sourceMappingURL=template.cjs.js.map
