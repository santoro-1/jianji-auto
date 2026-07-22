'use strict';

Object.defineProperty(exports, '__esModule', { value: true });

/**
 * @class
 * @category Core
 * @name EventHandler
 * @classdesc Base class that implements functionality for event handling
 * Inherit EventHandler to use its functionalities.
 * @sdk 9.8.0
 */
class EventHandler {
  constructor() {
    this._callbacks = {};
    this._callbackActive = {};
  }

  _addCallback(name, callback, scope, once = false) {
    if (!name || typeof name !== 'string' || !callback) return;
    if (!this._callbacks[name]) this._callbacks[name] = [];

    if (this._callbackActive[name] && this._callbackActive[name] === this._callbacks[name]) {
      this._callbackActive[name] = this._callbackActive[name].slice();
    }

    this._callbacks[name].push({
      callback: callback,
      scope: scope || this,
      once: once
    });
  }
  /**
   * @function
   * @name EventHandler#on
   * @description Attach an event handler to an event with the specified name.
   * @param {string} name
   * @param {any} callback
   * @param {any} scope
   * @return {EventHandler} This instance for chaining.
   * @sdk 9.8.0
   */


  on(name, callback, scope) {
    this._addCallback(name, callback, scope, false);

    return this;
  }
  /**
   * @function
   * @name EventHandler#off
   * @description Detach an event with a specific name, if there is no name provided, all the events are detached.
   * @param {string} name
   * @param {any} callback
   * @param {any} scope
   * @return {EventHandler} This instance for chaining.
   * @sdk 9.8.0
   */


  off(name, callback, scope) {
    if (name) {
      if (this._callbackActive[name] && this._callbackActive[name] === this._callbacks[name]) {
        this._callbackActive[name] = this._callbackActive[name].slice();
      }
    } else {
      for (const key in this._callbackActive) {
        if (!this._callbacks[key]) continue;
        if (this._callbacks[key] !== this._callbackActive[key]) continue;
        this._callbackActive[key] = this._callbackActive[key].slice();
      }
    }

    if (!name) {
      this._callbacks = {};
    } else if (!callback) {
      if (this._callbacks[name]) this._callbacks[name] = [];
    } else {
      const events = this._callbacks[name];
      if (!events) return this;
      let count = events.length;

      for (let i = 0; i < count; i++) {
        if (events[i].callback !== callback) continue;
        if (scope && events[i].scope !== scope) continue;
        events[i--] = events[--count];
      }

      events.length = count;
    }

    return this;
  }
  /**
   * @function
   * @name EventHandler#fire
   * @description Fire an event with a specified name,  the argument is passed to the event listener
   * @param {string} name
   * @param {any} arg1
   * @param {any} arg2
   * @param {any} arg3
   * @param {any} arg4
   * @param {any} arg5
   * @param {any} arg6
   * @param {any} arg7
   * @param {any} arg8
   * @return {EventHandler} This instance for chaining.
   * @sdk 9.8.0
   */


  fire(name, arg1, arg2, arg3, arg4, arg5, arg6, arg7, arg8) {
    if (!name || !this._callbacks[name]) return this;
    let callbacks;

    if (!this._callbackActive[name]) {
      this._callbackActive[name] = this._callbacks[name];
    } else {
      if (this._callbackActive[name] === this._callbacks[name]) {
        this._callbackActive[name] = this._callbackActive[name].slice();
      }

      callbacks = this._callbacks[name].slice();
    }

    for (let i = 0; (callbacks || this._callbackActive[name]) && i < (callbacks || this._callbackActive[name]).length; i++) {
      const evt = (callbacks || this._callbackActive[name])[i];
      evt.callback.call(evt.scope, arg1, arg2, arg3, arg4, arg5, arg6, arg7, arg8);

      if (evt.once) {
        const ind = this._callbacks[name].indexOf(evt);

        if (ind !== -1) {
          if (this._callbackActive[name] === this._callbacks[name]) {
            this._callbackActive[name] = this._callbackActive[name].slice();
          }

          this._callbacks[name].splice(ind, 1);
        }
      }
    }

    if (!callbacks) this._callbackActive[name] = undefined;
    return this;
  }
  /**
   * @function
   * @name EventHandler#once
   * @description Attach an event handler to an event. This handler will be removed after being fired once.
   * @param {string} name
   * @param {any} callback
   * @param {any} scope
   * @return {EventHandler} This instance for chaining.
   * @sdk 9.8.0
   */


  once(name, callback, scope) {
    this._addCallback(name, callback, scope, true);

    return this;
  }
  /**
   * @function
   * @name EventHandler#hasEvent
   * @description Test if there are any handlers bound to an event name.
   * @param {string} name
   * @return {boolean} True if the object has handlers bound to the specified event name.
   * @sdk 9.8.0
   */


  hasEvent(name) {
    return this._callbacks[name] && this._callbacks[name].length !== 0 || false;
  }

}

var Amaz$8 = effect.Amaz;
var Color$1 = Amaz$8.Color;
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
    const renderers = new Amaz$8.Vector();

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
      result = new Amaz$8.Vector4f(jsonArray[0], jsonArray[1], jsonArray[2], jsonArray[3]);
    }

    return result;
  };

  AmazUtils.CastJsonArray3fToAmazVector3f = function (jsonArray) {
    let result = null;

    if (jsonArray instanceof Array && jsonArray.length === 3) {
      result = new Amaz$8.Vector3f(jsonArray[0], jsonArray[1], jsonArray[2]);
    }

    return result;
  };

  AmazUtils.CastJsonArray2fToAmazVector2f = function (jsonArray) {
    let result = null;

    if (jsonArray instanceof Array && jsonArray.length === 2) {
      result = new Amaz$8.Vector2f(jsonArray[0], jsonArray[1]);
    }

    return result;
  };

  AmazUtils.CastJsonArrayToAmazVector = function (jsonArray) {
    const result = new Amaz$8.Vector();

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
      result = new Color$1(jsonArray[0], jsonArray[1], jsonArray[2], jsonArray[3]);
    }

    return result;
  };

  AmazUtils.CreateQuadMesh = function () {
    const fv = new Amaz$8.FloatVector();
    const ary = new Amaz$8.UInt16Vector();
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
    const quadMesh = new Amaz$8.Mesh();
    quadMesh.clearAfterUpload = true;
    quadMesh.vertices = fv;
    const posDesc = new Amaz$8.VertexAttribDesc();
    posDesc.semantic = Amaz$8.VertexAttribType.POSITION;
    const uvDesc = new Amaz$8.VertexAttribDesc();
    uvDesc.semantic = Amaz$8.VertexAttribType.TEXCOORD0;
    const vads = new Amaz$8.Vector();
    vads.pushBack(posDesc);
    vads.pushBack(uvDesc);
    quadMesh.vertexAttribs = vads;
    const aabb = new Amaz$8.AABB();
    aabb.min_x = -1.0;
    aabb.min_y = -1.0;
    aabb.min_z = 0.0;
    aabb.max_x = 1.0;
    aabb.max_y = 1.0;
    aabb.max_z = 0.0;
    quadMesh.boundingBox = aabb;
    const subMesh = new Amaz$8.SubMesh();
    ary.pushBack(0);
    ary.pushBack(1);
    ary.pushBack(2);
    ary.pushBack(3);
    subMesh.indices16 = ary;
    subMesh.primitive = Amaz$8.Primitive.TRIANGLE_FAN;
    subMesh.boundingBox = aabb;
    quadMesh.addSubMesh(subMesh);
    return quadMesh;
  };
})(AmazUtils || (AmazUtils = {}));

var AmazUtils$1 = AmazUtils;

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

var Amaz$7 = effect.Amaz;
var Quat = Amaz$7.Quaternionf;
var Vec2$3 = Amaz$7.Vector2f;
var Vec3$4 = Amaz$7.Vector3f;
const LAYER_SIZE = 120000000; // [0, 17)

const ORDER_SIZE = 40000; // [0, 2999)

const VEC3_UNIT_Z = new Vec3$4(0.0, 0.0, 1.0);
var WidgetType;

(function (WidgetType) {
  WidgetType[WidgetType["ROOT"] = 0] = "ROOT";
  WidgetType[WidgetType["SPRITE"] = 1] = "SPRITE";
  WidgetType[WidgetType["SHAPE"] = 2] = "SHAPE";
  WidgetType[WidgetType["TEXT"] = 3] = "TEXT";
})(WidgetType || (WidgetType = {}));

var WidgetResolutionType;

(function (WidgetResolutionType) {
  WidgetResolutionType[WidgetResolutionType["DESIGN"] = 0] = "DESIGN";
  WidgetResolutionType[WidgetResolutionType["DESIGN_HEIGHT"] = 1] = "DESIGN_HEIGHT";
  WidgetResolutionType[WidgetResolutionType["NORMALIZED"] = 2] = "NORMALIZED";
  WidgetResolutionType[WidgetResolutionType["ORIGINAL"] = 3] = "ORIGINAL";
})(WidgetResolutionType || (WidgetResolutionType = {})); // eslint-disable-next-line no-loss-of-precision


const PI = 3.14159265358979323846;
const TEMPLATE_TAG = 'AMAZINGTEMPLATE';
/**
 * @class
 * @category widget
 * @name Widget
 * @classdesc A Base class provides capabilities for Widget basic operations and properties,
 * move, scale, rotate, etc.
 * @description Constructor to create a Widget instance.
 * @author ninghualong
 * @sdk 12.2.0
 */

class Widget {
  constructor(name, widgetType, scene) {
    this.m_segmentStartTime = 0.0;
    this.m_segmentEndTime = 0.0;
    this.m_timeRange = new TimeRange(0.0, 0.0);
    this.m_enable = true; // m_cameraLayer is for renderEntiy is looked by which camera,
    // right now is by template.ts create camera entity,
    // which layerVisibleMask is Amaz.DynamicBitset(1, 1) by default.

    this.m_cameraLayer = 0;
    this.m_layer = 0;
    this.m_localOrder = 0; // the locale order in current layer

    this.m_position = new Vec3$4(0.0, 0.0, 0.0); // user set position

    this.m_scale = new Vec3$4(1.0, 1.0, 1.0); // user set scale

    this.m_rotation = new Vec3$4(0.0, 0.0, 0.0);
    this.m_rootEntity = null;
    this.m_constrainedWidgets = null;
    this.m_needUpdateConstrainedWidgets = false;
    this.m_widgetParamUpdated = true;
    this.m_updateOrder = true;
    this.m_needUpdateShapeBlendOrder = true;
    this.m_timeRangeUpdated = true;
    this.m_screenSizeChanged = true;
    this.m_widgetResolutionType = WidgetResolutionType.DESIGN;
    this.m_screenSize = new Vec2$3(720, 1280);
    this.m_pixelRatio = 640.0;
    this.m_extralScale = new Vec3$4(1.0, 1.0, 1.0); // different resolution type with different value

    this.m_orthoScale = 1.0;
    this.m_previewTime = 1.5;
    this.m_name = name;
    this.m_widgetType = widgetType;
    this.m_scene = scene;
  }

  get widgetName() {
    return this.m_name;
  }

  set position(pos) {
    if (!this.m_position.eq(pos)) {
      this.m_position = pos;
      this.m_widgetParamUpdated = true;
    }
  }

  get position() {
    return this.m_position;
  }

  set scale(scale) {
    if (!this.m_scale.eq(scale)) {
      this.m_scale = scale;
      this.m_widgetParamUpdated = true;
    }
  }

  get scale() {
    return this.m_scale;
  }

  set rotation(rotate) {
    if (!this.m_rotation.eq(rotate)) {
      this.m_rotation = rotate;
      this.m_widgetParamUpdated = true;
    }
  }

  get rotation() {
    return this.m_rotation;
  }

  set duration(duration) {
    if (this.duration !== duration && duration >= 0) {
      this.endTime = this.startTime + duration;
      this.m_widgetParamUpdated = true;
      this.m_timeRangeUpdated = true;
    }
  }

  get duration() {
    return this.m_timeRange.duration;
  }

  set layer(layer) {
    if (this.m_layer !== layer) {
      this.m_layer = layer;
      this.m_widgetParamUpdated = true;
      this.m_updateOrder = true;
      this.m_needUpdateShapeBlendOrder = true;
    }
  }

  get layer() {
    return this.m_layer;
  }

  get cameraLayer() {
    return this.m_cameraLayer;
  }

  set previewTime(timeStamp) {
    if (this.m_previewTime !== timeStamp) {
      this.m_previewTime = timeStamp;
    }
  }

  get previewTime() {
    return this.m_previewTime;
  }

  set localOrder(localOrder) {
    if (this.m_localOrder !== localOrder) {
      this.m_localOrder = localOrder;
      this.m_widgetParamUpdated = true;
      this.m_updateOrder = true;
      this.m_needUpdateShapeBlendOrder = true;
    }
  }

  get localOrder() {
    return this.m_localOrder;
  }

  set enable(enable) {
    if (this.m_enable !== enable) {
      this.m_enable = enable;
      this.m_widgetParamUpdated = true;
    }
  }

  get enable() {
    return this.m_enable;
  }

  get widgetType() {
    return this.m_widgetType;
  }

  set widgetResolutionType(resolutionType) {
    this.m_widgetResolutionType = resolutionType;
  }

  get widgetResolutionType() {
    return this.m_widgetResolutionType;
  }

  get scene() {
    return this.m_scene;
  }

  set rootEntity(root) {
    this.m_rootEntity = root;
  }

  get rootEntity() {
    if (!this.m_rootEntity) {
      this.createWidgetRootEntity(this.m_scene);
    }

    return this.m_rootEntity;
  }

  set startTime(startTime) {
    if (this.m_timeRange.startTime !== startTime) {
      this.m_timeRange.startTime = startTime;
      this.m_timeRangeUpdated = true;
    }
  }

  get startTime() {
    return this.m_timeRange.startTime;
  }

  set endTime(endTime) {
    if (this.m_timeRange.endTime !== endTime) {
      this.m_timeRange.endTime = endTime;
      this.m_timeRangeUpdated = true;
    }
  }

  get endTime() {
    return this.m_timeRange.endTime;
  }

  get screenSize() {
    return this.m_screenSize;
  }

  setTimeRange(startTime, endTime) {
    this.startTime = startTime;
    this.endTime = endTime;
  }

  setSegmentTimeRange(startTime, endTime, initTemplateDuration) {
    if (this.m_segmentStartTime !== startTime || this.m_segmentEndTime !== endTime) {
      // for segment time range change, need scale widget time range
      const new_duration = endTime - startTime;
      const old_duration = initTemplateDuration;

      if (old_duration !== 0) {
        const scale = new_duration / old_duration;
        const widget_old_duration = this.duration;
        this.startTime = startTime + scale * this.startTime;
        this.duration = scale * widget_old_duration;
        this.endTime = this.startTime + this.duration;
      } else {
        console.error('AMAZINGTEMPLATE', 'setSegmentTimeRange initTemplateDuration is 0');
      }
    }
  }

  set parameters(jsonParam) {
    if (jsonParam) {
      if ('position' in jsonParam) {
        const configPosition = AmazUtils$1.CastJsonArray3fToAmazVector3f(jsonParam.position);

        if (null !== configPosition) {
          this.position = configPosition;
        } else {
          console.error('widget set parameters json config position is not vector3f!');
        }
      }

      if ('scale' in jsonParam) {
        const configScale = AmazUtils$1.CastJsonArray3fToAmazVector3f(jsonParam.scale);

        if (null !== configScale) {
          this.scale = configScale;
        } else {
          console.error('widget set parameters json config scale is not vector3f!');
        }
      }

      if ('rotation' in jsonParam) {
        const configRotation = AmazUtils$1.CastJsonArray3fToAmazVector3f(jsonParam.rotation);

        if (null != configRotation) {
          this.rotation = configRotation;
        } else {
          console.error('widget set parameters json config rotation is not vector3f!');
        }
      }

      if ('layer' in jsonParam) {
        const configLayer = jsonParam.layer;
        this.layer = configLayer;
      }

      if ('preview_time' in jsonParam) {
        const configPreTime = jsonParam.preview_time;
        this.previewTime = configPreTime;
      } // set current widget is visible or not.


      if ('visible' in jsonParam) {
        const configEnable = jsonParam.visible;
        this.enable = configEnable;
      }

      if ('order_in_layer' in jsonParam) {
        const configLocalOrder = jsonParam.order_in_layer;
        this.localOrder = configLocalOrder;
      }

      let needUpdateEndTime = false;

      if ('start_time' in jsonParam) {
        const configStart_time = jsonParam.start_time;
        this.startTime = configStart_time;
        needUpdateEndTime = true;
      }

      if ('duration' in jsonParam) {
        const configDuration = jsonParam.duration;
        this.duration = configDuration;
        needUpdateEndTime = true;
      }

      if (needUpdateEndTime) {
        this.endTime = this.startTime + this.duration;
      }
    }
  }

  get parameters() {
    let typeStr = '';

    if (this.widgetType === WidgetType.ROOT) {
      typeStr = 'root';
    } else if (this.widgetType === WidgetType.SPRITE) {
      typeStr = 'sticker';
    } else if (this.widgetType === WidgetType.SHAPE) {
      typeStr = 'shape';
    } else if (this.widgetType === WidgetType.TEXT) {
      typeStr = 'text';
    }

    const widgetParam = {
      name: this.m_name,
      type: typeStr,
      layer: this.layer,
      order_in_layer: this.localOrder,
      preview_time: this.previewTime,
      start_time: this.startTime,
      duration: this.duration,
      position: [this.position.x, this.position.y, this.position.z],
      scale: [this.scale.x, this.scale.y, this.scale.z],
      rotation: [this.rotation.x, this.rotation.y, this.rotation.z]
    };
    return widgetParam;
  }

  onResize(screenSize, pixelRatio, extralScale) {
    this.m_screenSize = screenSize;
    this.m_pixelRatio = pixelRatio / this.m_orthoScale;
    this.m_extralScale = extralScale;
    this.m_screenSizeChanged = true;
    this.m_widgetParamUpdated = true;
  } // eslint-disable-next-line @typescript-eslint/no-unused-vars


  onUpdate(_timeStamp) {
    this.updateRootEntityParam();
  }

  getConstrainedWidgets() {
    return this.m_constrainedWidgets;
  }

  createWidgetRootEntity(scene) {
    this.m_rootEntity = AmazUtils$1.createEntity(this.m_name, scene);
    this.m_rootEntity.layer = this.m_cameraLayer; // add transform component to root entity

    this.m_rootEntity.transform = {
      position: new Vec3$4(0.0, 0.0, 0.0),
      scale: new Vec3$4(1.0, 1.0, 1.0),
      rotation: new Vec3$4(0.0, 0.0, 0.0)
    };
  }

  setWidgetRootEntity(root) {
    this.m_rootEntity = root;
  }

  getWidgetRootEntity() {
    return this.m_rootEntity;
  }

  removeWidgetRootEntity(scene) {
    if (null != this.m_rootEntity) {
      scene.removeEntity(this.m_rootEntity);
      this.m_rootEntity = null;
    }
  }

  updateConstrainedWidgets(name, widget) {
    if (null === this.m_constrainedWidgets) {
      this.m_constrainedWidgets = new Map();
      this.m_constrainedWidgets.set(name, widget);
    } else {
      if (!this.m_constrainedWidgets.has(name)) {
        this.m_constrainedWidgets.set(name, widget);
      }
    }
  }

  updateOrder(rootSortingOrder) {
    const renderers = AmazUtils$1.getRenderers(this.m_rootEntity);
    const size = renderers.size();

    for (let i = 0; i < size; i++) {
      const localOrder = 0;
      const renderer = renderers.get(i); // this logic code is not used, if custom need set order by event to table component

      /*
      const tableComp = renderer.entity.getComponent('TableComponent');
      if (tableComp && tableComp instanceof Amaz.TableComponent) {
        const orderKey: Amaz.Variant = 'local_order';
        if (tableComp.table.has(orderKey)) {
          const val = tableComp.table.get(orderKey);
          localOrder = val as number;
        }
      }
      */

      const sortingOrder = rootSortingOrder + localOrder;
      renderer.sortingOrder = sortingOrder;
    }
  }

  updateRootEntityParam() {
    if (this.m_widgetParamUpdated) {
      // update position, scale, rotation, layer
      {
        if (null != this.m_rootEntity) {
          // TODO: need set a bite dirty flag to reset those entity value
          this.m_rootEntity.visible = this.m_enable; // this logic is used for different resolution type, it's a special business logic

          const finalPosition = this.m_position.copy(); // if modify root widget use normalized coordinates, otherwise use pixel coordinates

          if (this.m_name === 'rootWidget') {
            finalPosition.x = 0.5 * this.m_position.x * this.m_screenSize.x / this.m_pixelRatio;
            finalPosition.y = 0.5 * this.m_position.y * this.m_screenSize.y / this.m_pixelRatio;
          } else {
            finalPosition.x = this.m_position.x / this.m_pixelRatio;
            finalPosition.y = this.m_position.y / this.m_pixelRatio;
          }

          const trans = this.m_rootEntity.getComponent('Transform');
          trans.localPosition = finalPosition;
          const widgetScale = this.m_scale.copy();
          trans.localScale = widgetScale.scale(this.m_extralScale); // LVPro rotation UI is negative to set value

          let rotatationQ = new Quat();
          rotatationQ = rotatationQ.axisAngleToQuaternion(VEC3_UNIT_Z, this.m_rotation.z / 180.0 * PI);
          trans.localOrientation = rotatationQ;
          const sortlayer = this.m_layer * LAYER_SIZE + this.m_localOrder * ORDER_SIZE; // root widget don't have real renderer, update child widget layer instead.
          // avoid updated for many times.

          if (this.m_name !== 'rootWidget' && this.m_updateOrder) {
            this.updateOrder(sortlayer);
            this.m_updateOrder = false;
          }
        }
      }
      this.m_widgetParamUpdated = false;
    }
  }

  checkIsInRange(timeStamp) {
    return this.compareFloatRange(this.m_timeRange.startTime, this.m_timeRange.endTime, timeStamp);
  }

  compareFloatRange(x, y, t, closedInterval = true) {
    const precision = 1e-6;

    const equal = (x, y) => Math.abs(x - y) < precision;

    return closedInterval ? t >= x && t <= y || equal(t, x) || equal(t, y) : t > x && t < y && !equal(t, x) && !equal(t, y);
  } // eslint-disable-next-line @typescript-eslint/no-unused-vars


  onUpdateAnimationDuration(_originTime, _newTime) {}

}

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

var Amaz$6 = effect.Amaz;
var AnimationType;

(function (AnimationType) {
  AnimationType[AnimationType["none"] = 0] = "none";
  AnimationType[AnimationType["in"] = 1] = "in";
  AnimationType[AnimationType["out"] = 2] = "out";
  AnimationType[AnimationType["loop"] = 3] = "loop";
})(AnimationType || (AnimationType = {}));

var ScriptType;

(function (ScriptType) {
  ScriptType[ScriptType["LUA"] = 0] = "LUA";
  ScriptType[ScriptType["JAVASCRIPT"] = 1] = "JAVASCRIPT";
})(ScriptType || (ScriptType = {}));

const prefabName = 'anim.prefab';
const contentFileName = '/content.json';
/**
 * @class
 * @category animation
 * @name Animation2D
 * @classdesc A widget2d animation class provides capabilities for animation
 * updating.
 * @description Constructor to create a Animation2D instance.
 * @author ninghualong
 * @sdk 12.2.0
 */

class Animation2D {
  constructor(path, resourceID, scriptType) {
    this.m_animationType = AnimationType.none;
    this.m_animationTimeRange = new TimeRange(0, 0);
    this.m_animationLoopDuration = 0;
    this.m_needResetAnimation = false;
    this.m_scriptComponet = null;
    this.m_state = {
      entered: false
    };
    this.m_prefabAnimComponent = undefined;
    this.m_animationPath = path;
    this.m_animationResourceID = resourceID;

    if (scriptType === 'js') {
      this.m_scriptType = ScriptType.JAVASCRIPT;
    } else {
      this.m_scriptType = ScriptType.LUA;
    }
  }

  set animationPath(path) {
    this.m_animationPath = path;
  }

  get animationPath() {
    return this.m_animationPath;
  }

  set animationType(ani_type) {
    this.m_animationType = ani_type;
  }

  get animationType() {
    return this.m_animationType;
  }

  get animationScriptType() {
    return this.m_scriptType;
  }

  get animationResourceID() {
    return this.m_animationResourceID;
  }

  set animationStartTime(start) {
    this.m_animationTimeRange.startTime = start;
  }

  get animationStartTime() {
    return this.m_animationTimeRange.startTime;
  }

  set animationEndTime(end) {
    this.m_animationTimeRange.endTime = end;
  }

  get animationEndTime() {
    return this.m_animationTimeRange.endTime;
  } // for loop animation set loop duration, which is different from animationDuration
  // this duration is used for script, eg: duration is 4, loop duration is 2,
  // then this animation will loop twice


  set animationLoopDuration(loop_duration) {
    var _a;

    this.m_animationLoopDuration = loop_duration;

    if (this.state.entered && this.animationType === AnimationType.loop && loop_duration > 0) {
      (_a = this.script) === null || _a === void 0 ? void 0 : _a.call('setDuration', [loop_duration]);
    }
  }

  get animationLoopDuration() {
    return this.m_animationLoopDuration;
  }

  set animationDuration(duration) {
    var _a;

    this.m_animationTimeRange.duration = duration;

    if (this.state.entered && this.animationType !== AnimationType.loop) {
      (_a = this.script) === null || _a === void 0 ? void 0 : _a.call('setDuration', [duration]);
    }
  }

  get animationDuration() {
    return this.m_animationTimeRange.duration;
  }

  get needResetAnimation() {
    return this.m_needResetAnimation;
  }

  get script() {
    return this.m_scriptComponet;
  }

  get state() {
    return this.m_state;
  }

  onEnter() {
    var _a, _b, _c;

    if (!this.m_state.entered) {
      if (this.animationType !== AnimationType.loop) {
        (_a = this.script) === null || _a === void 0 ? void 0 : _a.call('setDuration', [this.animationDuration]);
      } else {
        if (this.animationLoopDuration > 0) {
          (_b = this.script) === null || _b === void 0 ? void 0 : _b.call('setDuration', [this.animationLoopDuration]);
        }
      }

      (_c = this.script) === null || _c === void 0 ? void 0 : _c.call('onEnter');
      this.m_state.entered = true;
    }
  }

  onLeave() {
    var _a, _b, _c;

    if (this.m_state.entered) {
      if (this.m_animationType == AnimationType.in) {
        (_a = this.script) === null || _a === void 0 ? void 0 : _a.call('seek', [this.animationDuration]);
      } else if (this.m_animationType == AnimationType.out) {
        (_b = this.script) === null || _b === void 0 ? void 0 : _b.call('seek', [0]);
      }

      (_c = this.script) === null || _c === void 0 ? void 0 : _c.call('onLeave');
      this.m_state.entered = false;
    }
  }

  seek(timestamp) {
    var _a;

    if (this.state.entered) {
      let seekTime = timestamp - this.animationStartTime;
      if (seekTime < 0) seekTime = 0;
      (_a = this.script) === null || _a === void 0 ? void 0 : _a.call('seek', [seekTime]);
    }
  }

  onStart() {
    var _a;

    (_a = this.script) === null || _a === void 0 ? void 0 : _a.call('onStart');
  }

  onClear() {
    var _a;

    (_a = this.script) === null || _a === void 0 ? void 0 : _a.call('clear');
    this.m_state.entered = false;
  }

  get loaded() {
    return this.m_scriptComponet != null;
  }

  loadAnimation(path, entity) {
    const pm = Amaz$6.AmazingManager.getSingleton('PrefabManager');
    const anim = pm.loadPrefab(path, prefabName); // The correct logic only needs to include the else branch, the reason for including the if branch here is that LVPro allow list path not include animation path, so we assume that the prefab file is in the root directory by default. If the animation resource that generates the relative path needs to be limited to the version to 1450 or higher.

    if (anim) {
      this.m_prefabAnimComponent = anim.getRootEntity().getComponent('ScriptComponent');

      if (this.m_prefabAnimComponent) {
        this.m_scriptComponet = this.m_prefabAnimComponent.instantiate();
        const vec = new Amaz$6.Vector();
        vec.pushBack(this.m_scriptComponet);
        entity.components = vec;
      }
    } else {
      const contentPath = path + contentFileName;
      const contentJsonStr = AmazFileUtils.readFileContent(contentPath);

      if (contentJsonStr !== undefined) {
        const contentJson = JSON.parse(contentJsonStr);

        if (contentJson && 'filemap' in contentJson) {
          const fileMapJson = contentJson.filemap;

          if (fileMapJson && 'prefab' in fileMapJson) {
            const prefabFileName = fileMapJson.prefab;
            const anim = pm.loadPrefab(path, prefabFileName);

            if (anim) {
              this.m_prefabAnimComponent = anim.getRootEntity().getComponent('ScriptComponent');

              if (this.m_prefabAnimComponent) {
                this.m_scriptComponet = this.m_prefabAnimComponent.instantiate();
                const vec = new Amaz$6.Vector();
                vec.pushBack(this.m_scriptComponet);
                entity.components = vec;
              } else {
                console.error('AMAZINGTEMPLATE', 'loadAnimation failed!');
              }
            } else {
              console.error('AMAZINGTEMPLATE', 'Animation loadPrefab failed!');
            }
          } else {
            console.error('AMAZINGTEMPLATE', 'prefab key is not in filemap!');
          }
        } else {
          console.error('AMAZINGTEMPLATE', 'filemap key is not in contentJson!');
        }
      } else {
        console.error('AMAZINGTEMPLATE', 'contentJsonStr is undefined');
      }
    }

    return true;
  }

  unloadAnmation(entity) {
    if (null != this.m_scriptComponet) {
      this.onClear();
      entity.removeComponentCom(this.m_scriptComponet);
      this.m_scriptComponet = null;
    }
  }

  reloadAnimation(entity) {
    if (this.m_scriptComponet && this.m_prefabAnimComponent) {
      this.onClear();
      entity.removeComponentCom(this.m_scriptComponet);
      this.m_scriptComponet = this.m_prefabAnimComponent.instantiate();
      const vec = new Amaz$6.Vector();
      vec.pushBack(this.m_scriptComponet);
      entity.components = vec;
    }
  }

  resetAnimation() {
    if (this.m_needResetAnimation) ;
  }

}

var configValidator = {exports: {}};

configValidator.exports = validate20$5;

configValidator.exports.default = validate20$5;

function validate20$5(data, {
  instancePath = "",
  parentData,
  parentDataProperty,
  rootData = data
} = {}) {
  let vErrors = null;
  let errors = 0;

  {
    if (data && typeof data == "object" && !Array.isArray(data)) {
      let missing0;

      if (data.type === undefined && (missing0 = "type")) {
        validate20$5.errors = [{
          instancePath,
          schemaPath: "#/required",
          keyword: "required",
          params: {
            missingProperty: missing0
          },
          message: "must have required property '" + missing0 + "'"
        }];
        return false;
      } else {

        for (const key0 in data) {
          if (!(key0 === "type" || key0 === "root" || key0 === "children")) {
            validate20$5.errors = [{
              instancePath,
              schemaPath: "#/additionalProperties",
              keyword: "additionalProperties",
              params: {
                additionalProperty: key0
              },
              message: "must NOT have additional properties"
            }];
            return false;
          }
        }

        {
          if (data.type !== undefined) {
            const _errs2 = errors;

            if (typeof data.type !== "string") {
              validate20$5.errors = [{
                instancePath: instancePath + "/type",
                schemaPath: "#/properties/type/type",
                keyword: "type",
                params: {
                  type: "string"
                },
                message: "must be string"
              }];
              return false;
            }

            var valid0 = _errs2 === errors;
          } else {
            var valid0 = true;
          }

          if (valid0) {
            if (data.root !== undefined) {
              let data1 = data.root;
              const _errs4 = errors;

              if (!(data1 && typeof data1 == "object" && !Array.isArray(data1)) && data1 !== null) {
                validate20$5.errors = [{
                  instancePath: instancePath + "/root",
                  schemaPath: "#/properties/root/type",
                  keyword: "type",
                  params: {
                    type: "object"
                  },
                  message: "must be object"
                }];
                return false;
              }

              {
                if (data1 && typeof data1 == "object" && !Array.isArray(data1)) {
                  let missing1;

                  if (data1.name === undefined && (missing1 = "name") || data1.preview_time === undefined && (missing1 = "preview_time") || data1.duration === undefined && (missing1 = "duration")) {
                    validate20$5.errors = [{
                      instancePath: instancePath + "/root",
                      schemaPath: "#/properties/root/required",
                      keyword: "required",
                      params: {
                        missingProperty: missing1
                      },
                      message: "must have required property '" + missing1 + "'"
                    }];
                    return false;
                  } else {
                    if (data1.name !== undefined) {
                      const _errs7 = errors;

                      if (typeof data1.name !== "string") {
                        validate20$5.errors = [{
                          instancePath: instancePath + "/root/name",
                          schemaPath: "#/properties/root/properties/name/type",
                          keyword: "type",
                          params: {
                            type: "string"
                          },
                          message: "must be string"
                        }];
                        return false;
                      }

                      var valid1 = _errs7 === errors;
                    } else {
                      var valid1 = true;
                    }

                    if (valid1) {
                      if (data1.preview_time !== undefined) {
                        let data3 = data1.preview_time;
                        const _errs9 = errors;

                        if (!(typeof data3 == "number" && isFinite(data3))) {
                          validate20$5.errors = [{
                            instancePath: instancePath + "/root/preview_time",
                            schemaPath: "#/properties/root/properties/preview_time/type",
                            keyword: "type",
                            params: {
                              type: "number"
                            },
                            message: "must be number"
                          }];
                          return false;
                        }

                        var valid1 = _errs9 === errors;
                      } else {
                        var valid1 = true;
                      }

                      if (valid1) {
                        if (data1.duration !== undefined) {
                          let data4 = data1.duration;
                          const _errs11 = errors;

                          if (!(typeof data4 == "number" && isFinite(data4))) {
                            validate20$5.errors = [{
                              instancePath: instancePath + "/root/duration",
                              schemaPath: "#/properties/root/properties/duration/type",
                              keyword: "type",
                              params: {
                                type: "number"
                              },
                              message: "must be number"
                            }];
                            return false;
                          }

                          var valid1 = _errs11 === errors;
                        } else {
                          var valid1 = true;
                        }
                      }
                    }
                  }
                }
              }

              var valid0 = _errs4 === errors;
            } else {
              var valid0 = true;
            }

            if (valid0) {
              if (data.children !== undefined) {
                let data5 = data.children;
                const _errs13 = errors;

                if (!Array.isArray(data5) && data5 !== null) {
                  validate20$5.errors = [{
                    instancePath: instancePath + "/children",
                    schemaPath: "#/properties/children/type",
                    keyword: "type",
                    params: {
                      type: "array"
                    },
                    message: "must be array"
                  }];
                  return false;
                }

                {
                  if (Array.isArray(data5)) {
                    var valid2 = true;
                    const len0 = data5.length;

                    for (let i0 = 0; i0 < len0; i0++) {
                      let data6 = data5[i0];
                      const _errs16 = errors;

                      if (!(data6 && typeof data6 == "object" && !Array.isArray(data6))) {
                        validate20$5.errors = [{
                          instancePath: instancePath + "/children/" + i0,
                          schemaPath: "#/properties/children/items/type",
                          keyword: "type",
                          params: {
                            type: "object"
                          },
                          message: "must be object"
                        }];
                        return false;
                      }

                      var valid2 = _errs16 === errors;

                      if (!valid2) {
                        break;
                      }
                    }
                  }
                }

                var valid0 = _errs13 === errors;
              } else {
                var valid0 = true;
              }
            }
          }
        }
      }
    } else {
      validate20$5.errors = [{
        instancePath,
        schemaPath: "#/type",
        keyword: "type",
        params: {
          type: "object"
        },
        message: "must be object"
      }];
      return false;
    }
  }

  validate20$5.errors = vErrors;
  return errors === 0;
}

var spriteValidator = {exports: {}};

spriteValidator.exports = validate20$4;

spriteValidator.exports.default = validate20$4;

const schema22$4 = {
  "type": "object",
  "additionalProperties": true,
  "required": ["type"],
  "properties": {
    "name": {
      "type": "string",
      "nullable": false
    },
    "type": {
      "enum": ["text", "shape", "sticker"]
    },
    "position": {
      "type": "array",
      "items": {
        "type": "number"
      },
      "maxItems": 3,
      "minItems": 3
    },
    "rotation": {
      "type": "array",
      "items": {
        "type": "number"
      },
      "maxItems": 3,
      "minItems": 3
    },
    "scale": {
      "type": "array",
      "items": {
        "type": "number"
      },
      "maxItems": 3,
      "minItems": 3
    },
    "order_in_layer": {
      "type": "integer"
    },
    "start_time": {
      "type": "number"
    },
    "duration": {
      "type": "number"
    },
    "sticker_format": {
      "enum": ["png", "jpeg", "gif", "mp4", "seq"]
    },
    "sticker_design_type": {
      "enum": [0, 1]
    },
    "sticker_path": {
      "type": "string"
    },
    "sticker_resource_id": {
      "type": "string"
    },
    "resource_name_list": {
      "type": "array",
      "items": {
        "type": "string",
        "nullable": true
      }
    },
    "sticker_alpha": {
      "type": "number"
    },
    "sticker_flipX": {
      "type": "boolean"
    },
    "sticker_flipY": {
      "type": "boolean"
    },
    "fps": {
      "type": "number"
    },
    "sticker_loop": {
      "type": "boolean"
    },
    "anims": {
      "type": "array",
      "nullable": true,
      "items": {
        "type": "object"
      }
    }
  }
};

function validate20$4(data, {
  instancePath = "",
  parentData,
  parentDataProperty,
  rootData = data
} = {}) {
  let vErrors = null;
  let errors = 0;

  {
    if (data && typeof data == "object" && !Array.isArray(data)) {
      let missing0;

      if (data.type === undefined && (missing0 = "type")) {
        validate20$4.errors = [{
          instancePath,
          schemaPath: "#/required",
          keyword: "required",
          params: {
            missingProperty: missing0
          },
          message: "must have required property '" + missing0 + "'"
        }];
        return false;
      } else {
        if (data.name !== undefined) {
          const _errs2 = errors;

          if (typeof data.name !== "string") {
            validate20$4.errors = [{
              instancePath: instancePath + "/name",
              schemaPath: "#/properties/name/type",
              keyword: "type",
              params: {
                type: "string"
              },
              message: "must be string"
            }];
            return false;
          }

          var valid0 = _errs2 === errors;
        } else {
          var valid0 = true;
        }

        if (valid0) {
          if (data.type !== undefined) {
            let data1 = data.type;
            const _errs5 = errors;

            if (!(data1 === "text" || data1 === "shape" || data1 === "sticker")) {
              validate20$4.errors = [{
                instancePath: instancePath + "/type",
                schemaPath: "#/properties/type/enum",
                keyword: "enum",
                params: {
                  allowedValues: schema22$4.properties.type.enum
                },
                message: "must be equal to one of the allowed values"
              }];
              return false;
            }

            var valid0 = _errs5 === errors;
          } else {
            var valid0 = true;
          }

          if (valid0) {
            if (data.position !== undefined) {
              let data2 = data.position;
              const _errs6 = errors;

              {
                if (Array.isArray(data2)) {
                  if (data2.length > 3) {
                    validate20$4.errors = [{
                      instancePath: instancePath + "/position",
                      schemaPath: "#/properties/position/maxItems",
                      keyword: "maxItems",
                      params: {
                        limit: 3
                      },
                      message: "must NOT have more than 3 items"
                    }];
                    return false;
                  } else {
                    if (data2.length < 3) {
                      validate20$4.errors = [{
                        instancePath: instancePath + "/position",
                        schemaPath: "#/properties/position/minItems",
                        keyword: "minItems",
                        params: {
                          limit: 3
                        },
                        message: "must NOT have fewer than 3 items"
                      }];
                      return false;
                    } else {
                      var valid1 = true;
                      const len0 = data2.length;

                      for (let i0 = 0; i0 < len0; i0++) {
                        let data3 = data2[i0];
                        const _errs8 = errors;

                        if (!(typeof data3 == "number" && isFinite(data3))) {
                          validate20$4.errors = [{
                            instancePath: instancePath + "/position/" + i0,
                            schemaPath: "#/properties/position/items/type",
                            keyword: "type",
                            params: {
                              type: "number"
                            },
                            message: "must be number"
                          }];
                          return false;
                        }

                        var valid1 = _errs8 === errors;

                        if (!valid1) {
                          break;
                        }
                      }
                    }
                  }
                } else {
                  validate20$4.errors = [{
                    instancePath: instancePath + "/position",
                    schemaPath: "#/properties/position/type",
                    keyword: "type",
                    params: {
                      type: "array"
                    },
                    message: "must be array"
                  }];
                  return false;
                }
              }

              var valid0 = _errs6 === errors;
            } else {
              var valid0 = true;
            }

            if (valid0) {
              if (data.rotation !== undefined) {
                let data4 = data.rotation;
                const _errs10 = errors;

                {
                  if (Array.isArray(data4)) {
                    if (data4.length > 3) {
                      validate20$4.errors = [{
                        instancePath: instancePath + "/rotation",
                        schemaPath: "#/properties/rotation/maxItems",
                        keyword: "maxItems",
                        params: {
                          limit: 3
                        },
                        message: "must NOT have more than 3 items"
                      }];
                      return false;
                    } else {
                      if (data4.length < 3) {
                        validate20$4.errors = [{
                          instancePath: instancePath + "/rotation",
                          schemaPath: "#/properties/rotation/minItems",
                          keyword: "minItems",
                          params: {
                            limit: 3
                          },
                          message: "must NOT have fewer than 3 items"
                        }];
                        return false;
                      } else {
                        var valid2 = true;
                        const len1 = data4.length;

                        for (let i1 = 0; i1 < len1; i1++) {
                          let data5 = data4[i1];
                          const _errs12 = errors;

                          if (!(typeof data5 == "number" && isFinite(data5))) {
                            validate20$4.errors = [{
                              instancePath: instancePath + "/rotation/" + i1,
                              schemaPath: "#/properties/rotation/items/type",
                              keyword: "type",
                              params: {
                                type: "number"
                              },
                              message: "must be number"
                            }];
                            return false;
                          }

                          var valid2 = _errs12 === errors;

                          if (!valid2) {
                            break;
                          }
                        }
                      }
                    }
                  } else {
                    validate20$4.errors = [{
                      instancePath: instancePath + "/rotation",
                      schemaPath: "#/properties/rotation/type",
                      keyword: "type",
                      params: {
                        type: "array"
                      },
                      message: "must be array"
                    }];
                    return false;
                  }
                }

                var valid0 = _errs10 === errors;
              } else {
                var valid0 = true;
              }

              if (valid0) {
                if (data.scale !== undefined) {
                  let data6 = data.scale;
                  const _errs14 = errors;

                  {
                    if (Array.isArray(data6)) {
                      if (data6.length > 3) {
                        validate20$4.errors = [{
                          instancePath: instancePath + "/scale",
                          schemaPath: "#/properties/scale/maxItems",
                          keyword: "maxItems",
                          params: {
                            limit: 3
                          },
                          message: "must NOT have more than 3 items"
                        }];
                        return false;
                      } else {
                        if (data6.length < 3) {
                          validate20$4.errors = [{
                            instancePath: instancePath + "/scale",
                            schemaPath: "#/properties/scale/minItems",
                            keyword: "minItems",
                            params: {
                              limit: 3
                            },
                            message: "must NOT have fewer than 3 items"
                          }];
                          return false;
                        } else {
                          var valid3 = true;
                          const len2 = data6.length;

                          for (let i2 = 0; i2 < len2; i2++) {
                            let data7 = data6[i2];
                            const _errs16 = errors;

                            if (!(typeof data7 == "number" && isFinite(data7))) {
                              validate20$4.errors = [{
                                instancePath: instancePath + "/scale/" + i2,
                                schemaPath: "#/properties/scale/items/type",
                                keyword: "type",
                                params: {
                                  type: "number"
                                },
                                message: "must be number"
                              }];
                              return false;
                            }

                            var valid3 = _errs16 === errors;

                            if (!valid3) {
                              break;
                            }
                          }
                        }
                      }
                    } else {
                      validate20$4.errors = [{
                        instancePath: instancePath + "/scale",
                        schemaPath: "#/properties/scale/type",
                        keyword: "type",
                        params: {
                          type: "array"
                        },
                        message: "must be array"
                      }];
                      return false;
                    }
                  }

                  var valid0 = _errs14 === errors;
                } else {
                  var valid0 = true;
                }

                if (valid0) {
                  if (data.order_in_layer !== undefined) {
                    let data8 = data.order_in_layer;
                    const _errs18 = errors;

                    if (!(typeof data8 == "number" && !(data8 % 1) && !isNaN(data8) && isFinite(data8))) {
                      validate20$4.errors = [{
                        instancePath: instancePath + "/order_in_layer",
                        schemaPath: "#/properties/order_in_layer/type",
                        keyword: "type",
                        params: {
                          type: "integer"
                        },
                        message: "must be integer"
                      }];
                      return false;
                    }

                    var valid0 = _errs18 === errors;
                  } else {
                    var valid0 = true;
                  }

                  if (valid0) {
                    if (data.start_time !== undefined) {
                      let data9 = data.start_time;
                      const _errs20 = errors;

                      if (!(typeof data9 == "number" && isFinite(data9))) {
                        validate20$4.errors = [{
                          instancePath: instancePath + "/start_time",
                          schemaPath: "#/properties/start_time/type",
                          keyword: "type",
                          params: {
                            type: "number"
                          },
                          message: "must be number"
                        }];
                        return false;
                      }

                      var valid0 = _errs20 === errors;
                    } else {
                      var valid0 = true;
                    }

                    if (valid0) {
                      if (data.duration !== undefined) {
                        let data10 = data.duration;
                        const _errs22 = errors;

                        if (!(typeof data10 == "number" && isFinite(data10))) {
                          validate20$4.errors = [{
                            instancePath: instancePath + "/duration",
                            schemaPath: "#/properties/duration/type",
                            keyword: "type",
                            params: {
                              type: "number"
                            },
                            message: "must be number"
                          }];
                          return false;
                        }

                        var valid0 = _errs22 === errors;
                      } else {
                        var valid0 = true;
                      }

                      if (valid0) {
                        if (data.sticker_format !== undefined) {
                          let data11 = data.sticker_format;
                          const _errs24 = errors;

                          if (!(data11 === "png" || data11 === "jpeg" || data11 === "gif" || data11 === "mp4" || data11 === "seq")) {
                            validate20$4.errors = [{
                              instancePath: instancePath + "/sticker_format",
                              schemaPath: "#/properties/sticker_format/enum",
                              keyword: "enum",
                              params: {
                                allowedValues: schema22$4.properties.sticker_format.enum
                              },
                              message: "must be equal to one of the allowed values"
                            }];
                            return false;
                          }

                          var valid0 = _errs24 === errors;
                        } else {
                          var valid0 = true;
                        }

                        if (valid0) {
                          if (data.sticker_design_type !== undefined) {
                            let data12 = data.sticker_design_type;
                            const _errs25 = errors;

                            if (!(data12 === 0 || data12 === 1)) {
                              validate20$4.errors = [{
                                instancePath: instancePath + "/sticker_design_type",
                                schemaPath: "#/properties/sticker_design_type/enum",
                                keyword: "enum",
                                params: {
                                  allowedValues: schema22$4.properties.sticker_design_type.enum
                                },
                                message: "must be equal to one of the allowed values"
                              }];
                              return false;
                            }

                            var valid0 = _errs25 === errors;
                          } else {
                            var valid0 = true;
                          }

                          if (valid0) {
                            if (data.sticker_path !== undefined) {
                              const _errs26 = errors;

                              if (typeof data.sticker_path !== "string") {
                                validate20$4.errors = [{
                                  instancePath: instancePath + "/sticker_path",
                                  schemaPath: "#/properties/sticker_path/type",
                                  keyword: "type",
                                  params: {
                                    type: "string"
                                  },
                                  message: "must be string"
                                }];
                                return false;
                              }

                              var valid0 = _errs26 === errors;
                            } else {
                              var valid0 = true;
                            }

                            if (valid0) {
                              if (data.sticker_resource_id !== undefined) {
                                const _errs28 = errors;

                                if (typeof data.sticker_resource_id !== "string") {
                                  validate20$4.errors = [{
                                    instancePath: instancePath + "/sticker_resource_id",
                                    schemaPath: "#/properties/sticker_resource_id/type",
                                    keyword: "type",
                                    params: {
                                      type: "string"
                                    },
                                    message: "must be string"
                                  }];
                                  return false;
                                }

                                var valid0 = _errs28 === errors;
                              } else {
                                var valid0 = true;
                              }

                              if (valid0) {
                                if (data.resource_name_list !== undefined) {
                                  let data15 = data.resource_name_list;
                                  const _errs30 = errors;

                                  {
                                    if (Array.isArray(data15)) {
                                      var valid4 = true;
                                      const len3 = data15.length;

                                      for (let i3 = 0; i3 < len3; i3++) {
                                        let data16 = data15[i3];
                                        const _errs32 = errors;

                                        if (typeof data16 !== "string" && data16 !== null) {
                                          validate20$4.errors = [{
                                            instancePath: instancePath + "/resource_name_list/" + i3,
                                            schemaPath: "#/properties/resource_name_list/items/type",
                                            keyword: "type",
                                            params: {
                                              type: "string"
                                            },
                                            message: "must be string"
                                          }];
                                          return false;
                                        }

                                        var valid4 = _errs32 === errors;

                                        if (!valid4) {
                                          break;
                                        }
                                      }
                                    } else {
                                      validate20$4.errors = [{
                                        instancePath: instancePath + "/resource_name_list",
                                        schemaPath: "#/properties/resource_name_list/type",
                                        keyword: "type",
                                        params: {
                                          type: "array"
                                        },
                                        message: "must be array"
                                      }];
                                      return false;
                                    }
                                  }

                                  var valid0 = _errs30 === errors;
                                } else {
                                  var valid0 = true;
                                }

                                if (valid0) {
                                  if (data.sticker_alpha !== undefined) {
                                    let data17 = data.sticker_alpha;
                                    const _errs35 = errors;

                                    if (!(typeof data17 == "number" && isFinite(data17))) {
                                      validate20$4.errors = [{
                                        instancePath: instancePath + "/sticker_alpha",
                                        schemaPath: "#/properties/sticker_alpha/type",
                                        keyword: "type",
                                        params: {
                                          type: "number"
                                        },
                                        message: "must be number"
                                      }];
                                      return false;
                                    }

                                    var valid0 = _errs35 === errors;
                                  } else {
                                    var valid0 = true;
                                  }

                                  if (valid0) {
                                    if (data.sticker_flipX !== undefined) {
                                      const _errs37 = errors;

                                      if (typeof data.sticker_flipX !== "boolean") {
                                        validate20$4.errors = [{
                                          instancePath: instancePath + "/sticker_flipX",
                                          schemaPath: "#/properties/sticker_flipX/type",
                                          keyword: "type",
                                          params: {
                                            type: "boolean"
                                          },
                                          message: "must be boolean"
                                        }];
                                        return false;
                                      }

                                      var valid0 = _errs37 === errors;
                                    } else {
                                      var valid0 = true;
                                    }

                                    if (valid0) {
                                      if (data.sticker_flipY !== undefined) {
                                        const _errs39 = errors;

                                        if (typeof data.sticker_flipY !== "boolean") {
                                          validate20$4.errors = [{
                                            instancePath: instancePath + "/sticker_flipY",
                                            schemaPath: "#/properties/sticker_flipY/type",
                                            keyword: "type",
                                            params: {
                                              type: "boolean"
                                            },
                                            message: "must be boolean"
                                          }];
                                          return false;
                                        }

                                        var valid0 = _errs39 === errors;
                                      } else {
                                        var valid0 = true;
                                      }

                                      if (valid0) {
                                        if (data.fps !== undefined) {
                                          let data20 = data.fps;
                                          const _errs41 = errors;

                                          if (!(typeof data20 == "number" && isFinite(data20))) {
                                            validate20$4.errors = [{
                                              instancePath: instancePath + "/fps",
                                              schemaPath: "#/properties/fps/type",
                                              keyword: "type",
                                              params: {
                                                type: "number"
                                              },
                                              message: "must be number"
                                            }];
                                            return false;
                                          }

                                          var valid0 = _errs41 === errors;
                                        } else {
                                          var valid0 = true;
                                        }

                                        if (valid0) {
                                          if (data.sticker_loop !== undefined) {
                                            const _errs43 = errors;

                                            if (typeof data.sticker_loop !== "boolean") {
                                              validate20$4.errors = [{
                                                instancePath: instancePath + "/sticker_loop",
                                                schemaPath: "#/properties/sticker_loop/type",
                                                keyword: "type",
                                                params: {
                                                  type: "boolean"
                                                },
                                                message: "must be boolean"
                                              }];
                                              return false;
                                            }

                                            var valid0 = _errs43 === errors;
                                          } else {
                                            var valid0 = true;
                                          }

                                          if (valid0) {
                                            if (data.anims !== undefined) {
                                              let data22 = data.anims;
                                              const _errs45 = errors;

                                              if (!Array.isArray(data22) && data22 !== null) {
                                                validate20$4.errors = [{
                                                  instancePath: instancePath + "/anims",
                                                  schemaPath: "#/properties/anims/type",
                                                  keyword: "type",
                                                  params: {
                                                    type: "array"
                                                  },
                                                  message: "must be array"
                                                }];
                                                return false;
                                              }

                                              {
                                                if (Array.isArray(data22)) {
                                                  var valid5 = true;
                                                  const len4 = data22.length;

                                                  for (let i4 = 0; i4 < len4; i4++) {
                                                    let data23 = data22[i4];
                                                    const _errs48 = errors;

                                                    if (!(data23 && typeof data23 == "object" && !Array.isArray(data23))) {
                                                      validate20$4.errors = [{
                                                        instancePath: instancePath + "/anims/" + i4,
                                                        schemaPath: "#/properties/anims/items/type",
                                                        keyword: "type",
                                                        params: {
                                                          type: "object"
                                                        },
                                                        message: "must be object"
                                                      }];
                                                      return false;
                                                    }

                                                    var valid5 = _errs48 === errors;

                                                    if (!valid5) {
                                                      break;
                                                    }
                                                  }
                                                }
                                              }

                                              var valid0 = _errs45 === errors;
                                            } else {
                                              var valid0 = true;
                                            }
                                          }
                                        }
                                      }
                                    }
                                  }
                                }
                              }
                            }
                          }
                        }
                      }
                    }
                  }
                }
              }
            }
          }
        }
      }
    } else {
      validate20$4.errors = [{
        instancePath,
        schemaPath: "#/type",
        keyword: "type",
        params: {
          type: "object"
        },
        message: "must be object"
      }];
      return false;
    }
  }

  validate20$4.errors = vErrors;
  return errors === 0;
}

var widgetValidator = {exports: {}};

widgetValidator.exports = validate20$3;

widgetValidator.exports.default = validate20$3;

const schema22$3 = {
  "type": "object",
  "additionalProperties": true,
  "required": ["type"],
  "properties": {
    "type": {
      "enum": ["text", "shape", "sticker"]
    },
    "name": {
      "type": "string",
      "nullable": false
    }
  }
};

function validate20$3(data, {
  instancePath = "",
  parentData,
  parentDataProperty,
  rootData = data
} = {}) {
  let vErrors = null;
  let errors = 0;

  {
    if (data && typeof data == "object" && !Array.isArray(data)) {
      let missing0;

      if (data.type === undefined && (missing0 = "type")) {
        validate20$3.errors = [{
          instancePath,
          schemaPath: "#/required",
          keyword: "required",
          params: {
            missingProperty: missing0
          },
          message: "must have required property '" + missing0 + "'"
        }];
        return false;
      } else {
        if (data.type !== undefined) {
          let data0 = data.type;
          const _errs2 = errors;

          if (!(data0 === "text" || data0 === "shape" || data0 === "sticker")) {
            validate20$3.errors = [{
              instancePath: instancePath + "/type",
              schemaPath: "#/properties/type/enum",
              keyword: "enum",
              params: {
                allowedValues: schema22$3.properties.type.enum
              },
              message: "must be equal to one of the allowed values"
            }];
            return false;
          }

          var valid0 = _errs2 === errors;
        } else {
          var valid0 = true;
        }

        if (valid0) {
          if (data.name !== undefined) {
            const _errs3 = errors;

            if (typeof data.name !== "string") {
              validate20$3.errors = [{
                instancePath: instancePath + "/name",
                schemaPath: "#/properties/name/type",
                keyword: "type",
                params: {
                  type: "string"
                },
                message: "must be string"
              }];
              return false;
            }

            var valid0 = _errs3 === errors;
          } else {
            var valid0 = true;
          }
        }
      }
    } else {
      validate20$3.errors = [{
        instancePath,
        schemaPath: "#/type",
        keyword: "type",
        params: {
          type: "object"
        },
        message: "must be object"
      }];
      return false;
    }
  }

  validate20$3.errors = vErrors;
  return errors === 0;
}

var animValidator = {exports: {}};

animValidator.exports = validate20$2;

animValidator.exports.default = validate20$2;

const schema22$2 = {
  "type": "object",
  "required": ["anim_type"],
  "additionalProperties": false,
  "properties": {
    "anim_type": {
      "enum": ["in", "out", "loop"]
    },
    "anim_script_type": {
      "enum": ["lua", "js"]
    },
    "anim_resource_id": {
      "type": "string"
    },
    "anim_resource_path": {
      "type": "string"
    },
    "anim_start_time": {
      "type": "number"
    },
    "duration": {
      "type": "number"
    },
    "loop_duration": {
      "type": "number"
    }
  }
};

function validate20$2(data, {
  instancePath = "",
  parentData,
  parentDataProperty,
  rootData = data
} = {}) {
  let vErrors = null;
  let errors = 0;

  {
    if (data && typeof data == "object" && !Array.isArray(data)) {
      let missing0;

      if (data.anim_type === undefined && (missing0 = "anim_type")) {
        validate20$2.errors = [{
          instancePath,
          schemaPath: "#/required",
          keyword: "required",
          params: {
            missingProperty: missing0
          },
          message: "must have required property '" + missing0 + "'"
        }];
        return false;
      } else {

        for (const key0 in data) {
          if (!(key0 === "anim_type" || key0 === "anim_script_type" || key0 === "anim_resource_id" || key0 === "anim_resource_path" || key0 === "anim_start_time" || key0 === "duration" || key0 === "loop_duration")) {
            validate20$2.errors = [{
              instancePath,
              schemaPath: "#/additionalProperties",
              keyword: "additionalProperties",
              params: {
                additionalProperty: key0
              },
              message: "must NOT have additional properties"
            }];
            return false;
          }
        }

        {
          if (data.anim_type !== undefined) {
            let data0 = data.anim_type;
            const _errs2 = errors;

            if (!(data0 === "in" || data0 === "out" || data0 === "loop")) {
              validate20$2.errors = [{
                instancePath: instancePath + "/anim_type",
                schemaPath: "#/properties/anim_type/enum",
                keyword: "enum",
                params: {
                  allowedValues: schema22$2.properties.anim_type.enum
                },
                message: "must be equal to one of the allowed values"
              }];
              return false;
            }

            var valid0 = _errs2 === errors;
          } else {
            var valid0 = true;
          }

          if (valid0) {
            if (data.anim_script_type !== undefined) {
              let data1 = data.anim_script_type;
              const _errs3 = errors;

              if (!(data1 === "lua" || data1 === "js")) {
                validate20$2.errors = [{
                  instancePath: instancePath + "/anim_script_type",
                  schemaPath: "#/properties/anim_script_type/enum",
                  keyword: "enum",
                  params: {
                    allowedValues: schema22$2.properties.anim_script_type.enum
                  },
                  message: "must be equal to one of the allowed values"
                }];
                return false;
              }

              var valid0 = _errs3 === errors;
            } else {
              var valid0 = true;
            }

            if (valid0) {
              if (data.anim_resource_id !== undefined) {
                const _errs4 = errors;

                if (typeof data.anim_resource_id !== "string") {
                  validate20$2.errors = [{
                    instancePath: instancePath + "/anim_resource_id",
                    schemaPath: "#/properties/anim_resource_id/type",
                    keyword: "type",
                    params: {
                      type: "string"
                    },
                    message: "must be string"
                  }];
                  return false;
                }

                var valid0 = _errs4 === errors;
              } else {
                var valid0 = true;
              }

              if (valid0) {
                if (data.anim_resource_path !== undefined) {
                  const _errs6 = errors;

                  if (typeof data.anim_resource_path !== "string") {
                    validate20$2.errors = [{
                      instancePath: instancePath + "/anim_resource_path",
                      schemaPath: "#/properties/anim_resource_path/type",
                      keyword: "type",
                      params: {
                        type: "string"
                      },
                      message: "must be string"
                    }];
                    return false;
                  }

                  var valid0 = _errs6 === errors;
                } else {
                  var valid0 = true;
                }

                if (valid0) {
                  if (data.anim_start_time !== undefined) {
                    let data4 = data.anim_start_time;
                    const _errs8 = errors;

                    if (!(typeof data4 == "number" && isFinite(data4))) {
                      validate20$2.errors = [{
                        instancePath: instancePath + "/anim_start_time",
                        schemaPath: "#/properties/anim_start_time/type",
                        keyword: "type",
                        params: {
                          type: "number"
                        },
                        message: "must be number"
                      }];
                      return false;
                    }

                    var valid0 = _errs8 === errors;
                  } else {
                    var valid0 = true;
                  }

                  if (valid0) {
                    if (data.duration !== undefined) {
                      let data5 = data.duration;
                      const _errs10 = errors;

                      if (!(typeof data5 == "number" && isFinite(data5))) {
                        validate20$2.errors = [{
                          instancePath: instancePath + "/duration",
                          schemaPath: "#/properties/duration/type",
                          keyword: "type",
                          params: {
                            type: "number"
                          },
                          message: "must be number"
                        }];
                        return false;
                      }

                      var valid0 = _errs10 === errors;
                    } else {
                      var valid0 = true;
                    }

                    if (valid0) {
                      if (data.loop_duration !== undefined) {
                        let data6 = data.loop_duration;
                        const _errs12 = errors;

                        if (!(typeof data6 == "number" && isFinite(data6))) {
                          validate20$2.errors = [{
                            instancePath: instancePath + "/loop_duration",
                            schemaPath: "#/properties/loop_duration/type",
                            keyword: "type",
                            params: {
                              type: "number"
                            },
                            message: "must be number"
                          }];
                          return false;
                        }

                        var valid0 = _errs12 === errors;
                      } else {
                        var valid0 = true;
                      }
                    }
                  }
                }
              }
            }
          }
        }
      }
    } else {
      validate20$2.errors = [{
        instancePath,
        schemaPath: "#/type",
        keyword: "type",
        params: {
          type: "object"
        },
        message: "must be object"
      }];
      return false;
    }
  }

  validate20$2.errors = vErrors;
  return errors === 0;
}

var dependValidator = {exports: {}};

dependValidator.exports = validate20$1;

dependValidator.exports.default = validate20$1;

const schema22$1 = {
  "type": "object",
  "required": ["depend_resource_list"],
  "additionalProperties": false,
  "properties": {
    "depend_resource_list": {
      "type": "array",
      "nullable": true,
      "items": {
        "type": "object",
        "required": ["type", "resource_id"],
        "additionalProperties": false,
        "properties": {
          "type": {
            "enum": ["fonts", "text_animation", "sticker_animation", "shape_animation", "sticker_resource", "flower"]
          },
          "resource_id": {
            "type": "string"
          },
          "resource_path": {}
        }
      }
    }
  }
};

function validate20$1(data, {
  instancePath = "",
  parentData,
  parentDataProperty,
  rootData = data
} = {}) {
  let vErrors = null;
  let errors = 0;

  {
    if (data && typeof data == "object" && !Array.isArray(data)) {
      let missing0;

      if (data.depend_resource_list === undefined && (missing0 = "depend_resource_list")) {
        validate20$1.errors = [{
          instancePath,
          schemaPath: "#/required",
          keyword: "required",
          params: {
            missingProperty: missing0
          },
          message: "must have required property '" + missing0 + "'"
        }];
        return false;
      } else {

        for (const key0 in data) {
          if (!(key0 === "depend_resource_list")) {
            validate20$1.errors = [{
              instancePath,
              schemaPath: "#/additionalProperties",
              keyword: "additionalProperties",
              params: {
                additionalProperty: key0
              },
              message: "must NOT have additional properties"
            }];
            return false;
          }
        }

        {
          if (data.depend_resource_list !== undefined) {
            let data0 = data.depend_resource_list;

            if (!Array.isArray(data0) && data0 !== null) {
              validate20$1.errors = [{
                instancePath: instancePath + "/depend_resource_list",
                schemaPath: "#/properties/depend_resource_list/type",
                keyword: "type",
                params: {
                  type: "array"
                },
                message: "must be array"
              }];
              return false;
            }

            {
              if (Array.isArray(data0)) {
                var valid1 = true;
                const len0 = data0.length;

                for (let i0 = 0; i0 < len0; i0++) {
                  let data1 = data0[i0];
                  const _errs5 = errors;

                  {
                    if (data1 && typeof data1 == "object" && !Array.isArray(data1)) {
                      let missing1;

                      if (data1.type === undefined && (missing1 = "type") || data1.resource_id === undefined && (missing1 = "resource_id")) {
                        validate20$1.errors = [{
                          instancePath: instancePath + "/depend_resource_list/" + i0,
                          schemaPath: "#/properties/depend_resource_list/items/required",
                          keyword: "required",
                          params: {
                            missingProperty: missing1
                          },
                          message: "must have required property '" + missing1 + "'"
                        }];
                        return false;
                      } else {

                        for (const key1 in data1) {
                          if (!(key1 === "type" || key1 === "resource_id" || key1 === "resource_path")) {
                            validate20$1.errors = [{
                              instancePath: instancePath + "/depend_resource_list/" + i0,
                              schemaPath: "#/properties/depend_resource_list/items/additionalProperties",
                              keyword: "additionalProperties",
                              params: {
                                additionalProperty: key1
                              },
                              message: "must NOT have additional properties"
                            }];
                            return false;
                          }
                        }

                        {
                          if (data1.type !== undefined) {
                            let data2 = data1.type;
                            const _errs8 = errors;

                            if (!(data2 === "fonts" || data2 === "text_animation" || data2 === "sticker_animation" || data2 === "shape_animation" || data2 === "sticker_resource" || data2 === "flower")) {
                              validate20$1.errors = [{
                                instancePath: instancePath + "/depend_resource_list/" + i0 + "/type",
                                schemaPath: "#/properties/depend_resource_list/items/properties/type/enum",
                                keyword: "enum",
                                params: {
                                  allowedValues: schema22$1.properties.depend_resource_list.items.properties.type.enum
                                },
                                message: "must be equal to one of the allowed values"
                              }];
                              return false;
                            }

                            var valid2 = _errs8 === errors;
                          } else {
                            var valid2 = true;
                          }

                          if (valid2) {
                            if (data1.resource_id !== undefined) {
                              const _errs9 = errors;

                              if (typeof data1.resource_id !== "string") {
                                validate20$1.errors = [{
                                  instancePath: instancePath + "/depend_resource_list/" + i0 + "/resource_id",
                                  schemaPath: "#/properties/depend_resource_list/items/properties/resource_id/type",
                                  keyword: "type",
                                  params: {
                                    type: "string"
                                  },
                                  message: "must be string"
                                }];
                                return false;
                              }

                              var valid2 = _errs9 === errors;
                            } else {
                              var valid2 = true;
                            }
                          }
                        }
                      }
                    } else {
                      validate20$1.errors = [{
                        instancePath: instancePath + "/depend_resource_list/" + i0,
                        schemaPath: "#/properties/depend_resource_list/items/type",
                        keyword: "type",
                        params: {
                          type: "object"
                        },
                        message: "must be object"
                      }];
                      return false;
                    }
                  }

                  var valid1 = _errs5 === errors;

                  if (!valid1) {
                    break;
                  }
                }
              }
            }
          }
        }
      }
    } else {
      validate20$1.errors = [{
        instancePath,
        schemaPath: "#/type",
        keyword: "type",
        params: {
          type: "object"
        },
        message: "must be object"
      }];
      return false;
    }
  }

  validate20$1.errors = vErrors;
  return errors === 0;
}

var textValidator = {exports: {}};

textValidator.exports = validate20;

textValidator.exports.default = validate20;

const schema22 = {
  "type": "object",
  "additionalProperties": true,
  "required": ["type"],
  "properties": {
    "name": {
      "type": "string",
      "nullable": false
    },
    "type": {
      "enum": ["text"]
    },
    "position": {
      "type": "array",
      "items": {
        "type": "number"
      },
      "maxItems": 3,
      "minItems": 3
    },
    "rotation": {
      "type": "array",
      "items": {
        "type": "number"
      },
      "maxItems": 3,
      "minItems": 3
    },
    "scale": {
      "type": "array",
      "items": {
        "type": "number"
      },
      "maxItems": 3,
      "minItems": 3
    },
    "order_in_layer": {
      "type": "integer"
    },
    "start_time": {
      "type": "number"
    },
    "duration": {
      "type": "number"
    },
    "text_params": {
      "type": "object",
      "additionalProperties": true,
      "properties": {
        "richText": {
          "type": "string"
        }
      }
    },
    "anims": {
      "type": "array",
      "nullable": true,
      "items": {
        "type": "object"
      }
    }
  }
};

function validate20(data, {
  instancePath = "",
  parentData,
  parentDataProperty,
  rootData = data
} = {}) {
  let vErrors = null;
  let errors = 0;

  {
    if (data && typeof data == "object" && !Array.isArray(data)) {
      let missing0;

      if (data.type === undefined && (missing0 = "type")) {
        validate20.errors = [{
          instancePath,
          schemaPath: "#/required",
          keyword: "required",
          params: {
            missingProperty: missing0
          },
          message: "must have required property '" + missing0 + "'"
        }];
        return false;
      } else {
        if (data.name !== undefined) {
          const _errs2 = errors;

          if (typeof data.name !== "string") {
            validate20.errors = [{
              instancePath: instancePath + "/name",
              schemaPath: "#/properties/name/type",
              keyword: "type",
              params: {
                type: "string"
              },
              message: "must be string"
            }];
            return false;
          }

          var valid0 = _errs2 === errors;
        } else {
          var valid0 = true;
        }

        if (valid0) {
          if (data.type !== undefined) {
            const _errs5 = errors;

            if (!(data.type === "text")) {
              validate20.errors = [{
                instancePath: instancePath + "/type",
                schemaPath: "#/properties/type/enum",
                keyword: "enum",
                params: {
                  allowedValues: schema22.properties.type.enum
                },
                message: "must be equal to one of the allowed values"
              }];
              return false;
            }

            var valid0 = _errs5 === errors;
          } else {
            var valid0 = true;
          }

          if (valid0) {
            if (data.position !== undefined) {
              let data2 = data.position;
              const _errs6 = errors;

              {
                if (Array.isArray(data2)) {
                  if (data2.length > 3) {
                    validate20.errors = [{
                      instancePath: instancePath + "/position",
                      schemaPath: "#/properties/position/maxItems",
                      keyword: "maxItems",
                      params: {
                        limit: 3
                      },
                      message: "must NOT have more than 3 items"
                    }];
                    return false;
                  } else {
                    if (data2.length < 3) {
                      validate20.errors = [{
                        instancePath: instancePath + "/position",
                        schemaPath: "#/properties/position/minItems",
                        keyword: "minItems",
                        params: {
                          limit: 3
                        },
                        message: "must NOT have fewer than 3 items"
                      }];
                      return false;
                    } else {
                      var valid1 = true;
                      const len0 = data2.length;

                      for (let i0 = 0; i0 < len0; i0++) {
                        let data3 = data2[i0];
                        const _errs8 = errors;

                        if (!(typeof data3 == "number" && isFinite(data3))) {
                          validate20.errors = [{
                            instancePath: instancePath + "/position/" + i0,
                            schemaPath: "#/properties/position/items/type",
                            keyword: "type",
                            params: {
                              type: "number"
                            },
                            message: "must be number"
                          }];
                          return false;
                        }

                        var valid1 = _errs8 === errors;

                        if (!valid1) {
                          break;
                        }
                      }
                    }
                  }
                } else {
                  validate20.errors = [{
                    instancePath: instancePath + "/position",
                    schemaPath: "#/properties/position/type",
                    keyword: "type",
                    params: {
                      type: "array"
                    },
                    message: "must be array"
                  }];
                  return false;
                }
              }

              var valid0 = _errs6 === errors;
            } else {
              var valid0 = true;
            }

            if (valid0) {
              if (data.rotation !== undefined) {
                let data4 = data.rotation;
                const _errs10 = errors;

                {
                  if (Array.isArray(data4)) {
                    if (data4.length > 3) {
                      validate20.errors = [{
                        instancePath: instancePath + "/rotation",
                        schemaPath: "#/properties/rotation/maxItems",
                        keyword: "maxItems",
                        params: {
                          limit: 3
                        },
                        message: "must NOT have more than 3 items"
                      }];
                      return false;
                    } else {
                      if (data4.length < 3) {
                        validate20.errors = [{
                          instancePath: instancePath + "/rotation",
                          schemaPath: "#/properties/rotation/minItems",
                          keyword: "minItems",
                          params: {
                            limit: 3
                          },
                          message: "must NOT have fewer than 3 items"
                        }];
                        return false;
                      } else {
                        var valid2 = true;
                        const len1 = data4.length;

                        for (let i1 = 0; i1 < len1; i1++) {
                          let data5 = data4[i1];
                          const _errs12 = errors;

                          if (!(typeof data5 == "number" && isFinite(data5))) {
                            validate20.errors = [{
                              instancePath: instancePath + "/rotation/" + i1,
                              schemaPath: "#/properties/rotation/items/type",
                              keyword: "type",
                              params: {
                                type: "number"
                              },
                              message: "must be number"
                            }];
                            return false;
                          }

                          var valid2 = _errs12 === errors;

                          if (!valid2) {
                            break;
                          }
                        }
                      }
                    }
                  } else {
                    validate20.errors = [{
                      instancePath: instancePath + "/rotation",
                      schemaPath: "#/properties/rotation/type",
                      keyword: "type",
                      params: {
                        type: "array"
                      },
                      message: "must be array"
                    }];
                    return false;
                  }
                }

                var valid0 = _errs10 === errors;
              } else {
                var valid0 = true;
              }

              if (valid0) {
                if (data.scale !== undefined) {
                  let data6 = data.scale;
                  const _errs14 = errors;

                  {
                    if (Array.isArray(data6)) {
                      if (data6.length > 3) {
                        validate20.errors = [{
                          instancePath: instancePath + "/scale",
                          schemaPath: "#/properties/scale/maxItems",
                          keyword: "maxItems",
                          params: {
                            limit: 3
                          },
                          message: "must NOT have more than 3 items"
                        }];
                        return false;
                      } else {
                        if (data6.length < 3) {
                          validate20.errors = [{
                            instancePath: instancePath + "/scale",
                            schemaPath: "#/properties/scale/minItems",
                            keyword: "minItems",
                            params: {
                              limit: 3
                            },
                            message: "must NOT have fewer than 3 items"
                          }];
                          return false;
                        } else {
                          var valid3 = true;
                          const len2 = data6.length;

                          for (let i2 = 0; i2 < len2; i2++) {
                            let data7 = data6[i2];
                            const _errs16 = errors;

                            if (!(typeof data7 == "number" && isFinite(data7))) {
                              validate20.errors = [{
                                instancePath: instancePath + "/scale/" + i2,
                                schemaPath: "#/properties/scale/items/type",
                                keyword: "type",
                                params: {
                                  type: "number"
                                },
                                message: "must be number"
                              }];
                              return false;
                            }

                            var valid3 = _errs16 === errors;

                            if (!valid3) {
                              break;
                            }
                          }
                        }
                      }
                    } else {
                      validate20.errors = [{
                        instancePath: instancePath + "/scale",
                        schemaPath: "#/properties/scale/type",
                        keyword: "type",
                        params: {
                          type: "array"
                        },
                        message: "must be array"
                      }];
                      return false;
                    }
                  }

                  var valid0 = _errs14 === errors;
                } else {
                  var valid0 = true;
                }

                if (valid0) {
                  if (data.order_in_layer !== undefined) {
                    let data8 = data.order_in_layer;
                    const _errs18 = errors;

                    if (!(typeof data8 == "number" && !(data8 % 1) && !isNaN(data8) && isFinite(data8))) {
                      validate20.errors = [{
                        instancePath: instancePath + "/order_in_layer",
                        schemaPath: "#/properties/order_in_layer/type",
                        keyword: "type",
                        params: {
                          type: "integer"
                        },
                        message: "must be integer"
                      }];
                      return false;
                    }

                    var valid0 = _errs18 === errors;
                  } else {
                    var valid0 = true;
                  }

                  if (valid0) {
                    if (data.start_time !== undefined) {
                      let data9 = data.start_time;
                      const _errs20 = errors;

                      if (!(typeof data9 == "number" && isFinite(data9))) {
                        validate20.errors = [{
                          instancePath: instancePath + "/start_time",
                          schemaPath: "#/properties/start_time/type",
                          keyword: "type",
                          params: {
                            type: "number"
                          },
                          message: "must be number"
                        }];
                        return false;
                      }

                      var valid0 = _errs20 === errors;
                    } else {
                      var valid0 = true;
                    }

                    if (valid0) {
                      if (data.duration !== undefined) {
                        let data10 = data.duration;
                        const _errs22 = errors;

                        if (!(typeof data10 == "number" && isFinite(data10))) {
                          validate20.errors = [{
                            instancePath: instancePath + "/duration",
                            schemaPath: "#/properties/duration/type",
                            keyword: "type",
                            params: {
                              type: "number"
                            },
                            message: "must be number"
                          }];
                          return false;
                        }

                        var valid0 = _errs22 === errors;
                      } else {
                        var valid0 = true;
                      }

                      if (valid0) {
                        if (data.text_params !== undefined) {
                          let data11 = data.text_params;
                          const _errs24 = errors;

                          {
                            if (data11 && typeof data11 == "object" && !Array.isArray(data11)) {
                              if (data11.richText !== undefined) {
                                if (typeof data11.richText !== "string") {
                                  validate20.errors = [{
                                    instancePath: instancePath + "/text_params/richText",
                                    schemaPath: "#/properties/text_params/properties/richText/type",
                                    keyword: "type",
                                    params: {
                                      type: "string"
                                    },
                                    message: "must be string"
                                  }];
                                  return false;
                                }
                              }
                            } else {
                              validate20.errors = [{
                                instancePath: instancePath + "/text_params",
                                schemaPath: "#/properties/text_params/type",
                                keyword: "type",
                                params: {
                                  type: "object"
                                },
                                message: "must be object"
                              }];
                              return false;
                            }
                          }

                          var valid0 = _errs24 === errors;
                        } else {
                          var valid0 = true;
                        }

                        if (valid0) {
                          if (data.anims !== undefined) {
                            let data13 = data.anims;
                            const _errs29 = errors;

                            if (!Array.isArray(data13) && data13 !== null) {
                              validate20.errors = [{
                                instancePath: instancePath + "/anims",
                                schemaPath: "#/properties/anims/type",
                                keyword: "type",
                                params: {
                                  type: "array"
                                },
                                message: "must be array"
                              }];
                              return false;
                            }

                            {
                              if (Array.isArray(data13)) {
                                var valid5 = true;
                                const len3 = data13.length;

                                for (let i3 = 0; i3 < len3; i3++) {
                                  let data14 = data13[i3];
                                  const _errs32 = errors;

                                  if (!(data14 && typeof data14 == "object" && !Array.isArray(data14))) {
                                    validate20.errors = [{
                                      instancePath: instancePath + "/anims/" + i3,
                                      schemaPath: "#/properties/anims/items/type",
                                      keyword: "type",
                                      params: {
                                        type: "object"
                                      },
                                      message: "must be object"
                                    }];
                                    return false;
                                  }

                                  var valid5 = _errs32 === errors;

                                  if (!valid5) {
                                    break;
                                  }
                                }
                              }
                            }

                            var valid0 = _errs29 === errors;
                          } else {
                            var valid0 = true;
                          }
                        }
                      }
                    }
                  }
                }
              }
            }
          }
        }
      }
    } else {
      validate20.errors = [{
        instancePath,
        schemaPath: "#/type",
        keyword: "type",
        params: {
          type: "object"
        },
        message: "must be object"
      }];
      return false;
    }
  }

  validate20.errors = vErrors;
  return errors === 0;
}

class TemplateConfigParser {
  static parseConfig(configStr) {
    const config = configStringToObject(configStr);

    if (TemplateConfigParser.useValidator) {
      const validator = configValidator.exports;

      if (validator(config, {
        rootData: config
      })) {
        // configStr is ConfigData type here
        if (config.type === 'ScriptTemplate') {
          return config;
        }
      } else {
        console.error('AMAZINGTEMPLATE', 'TemplateConfigParser', JSON.stringify(validator.errors));
        return undefined;
      }
    }

    return config;
  }

  static parseChildNode(configStr) {
    const config = configStringToObject(configStr);

    if (TemplateConfigParser.useValidator) {
      const validator = widgetValidator.exports; // A useless second parameter must be written here, otherwise quickjs will report an error.

      if (validator(config, {
        rootData: config
      })) {
        return config;
      } else {
        console.error('AMAZINGTEMPLATE', 'parseChildNode', JSON.stringify(validator.errors));
        return undefined;
      }
    }

    return config;
  }

  static parseSpriteConfig(configStr) {
    const config = configStringToObject(configStr);

    if (TemplateConfigParser.useValidator) {
      const validator = spriteValidator.exports;

      if (validator(config, {
        rootData: config
      })) {
        return config;
      } else {
        console.error('AMAZINGTEMPLATE', 'parseSpriteConfig', JSON.stringify(validator.errors));
        return undefined;
      }
    }

    return config;
  }

  static parseTextConfig(configStr) {
    const config = configStringToObject(configStr);

    if (TemplateConfigParser.useValidator) {
      const validator = textValidator.exports;

      if (validator(config, {
        rootData: config
      })) {
        return config;
      } else {
        console.error('AMAZINGTEMPLATE', 'parseTextConfig', JSON.stringify(validator.errors));
        return undefined;
      }
    }

    return config;
  }

  static parseAnimationConfig(configStr) {
    const config = configStringToObject(configStr);

    if (TemplateConfigParser.useValidator) {
      const validator = animValidator.exports;

      if (validator(config, {
        rootData: config
      })) {
        return config;
      } else {
        console.error('AMAZINGTEMPLATE', 'parseAnimationConfig', JSON.stringify(validator.errors));
        return undefined;
      }
    }

    return config;
  }

  static parseDependConfig(configStr) {
    const config = configStringToObject(configStr);

    if (TemplateConfigParser.useValidator) {
      const validator = dependValidator.exports;

      if (validator(config, {
        rootData: config
      })) {
        return config;
      } else {
        console.error('AMAZINGTEMPLATE', 'parseDependConfig', JSON.stringify(validator.errors));
        return undefined;
      }
    }

    return config;
  }

}
TemplateConfigParser.useValidator = true;

function configStringToObject(configStr) {
  let config = configStr;

  if (typeof configStr == 'string') {
    config = JSON.parse(configStr);
  }

  return config;
}

var Amaz$5 = effect.Amaz;
var Rect$1 = Amaz$5.Rect;
var Vec2$2 = Amaz$5.Vector2f;
var Vec3$3 = Amaz$5.Vector3f;
/**
 * @class
 * @category widget2d
 * @name Widget2D
 * @classdesc A widget2d class provides capabilities for 2d widget, which
 * inherited from widget.
 * @description Constructor to create a Widget2D instance.
 * @author ninghualong
 * @sdk 12.2.0
 */

class Widget2D extends Widget {
  constructor(name, widgetType, scene) {
    super(name, widgetType, scene);
    this.m_anchor = new Vec2$2(0.0, 0.0); // bindingBox is using box center position width and height as a
    // vector4f to describe structure data, like:(x, y, w, h)

    this.m_layoutParams = null;
    this.m_bindingBox = new Rect$1(0.0, 0.0, 0.0, 0.0);
    this.m_animations = null;
    this.m_scriptPassthroughParamsDirty = false;
    this.m_renderEntity = null;
    this.m_widgetOriginalPixelSize = new Vec2$2(0.0, 0.0);
    this.m_widgetOriginalSize = new Vec2$2(0.0, 0.0); // normalized，-1～1

    this.m_normalizedSize = new Vec2$2(0.0, 0.0); // normalized，-1～1, which is for custom using

    this.m_originalPixelSizeDirty = false;
    this.m_scriptPassthroughParams = new Map();
  }

  set anchor(anchor) {
    this.m_anchor = anchor;
  }

  get anchor() {
    return this.m_anchor;
  }

  get bindingBox() {
    return this.m_bindingBox;
  }

  set layoutParams(layout) {
    this.m_layoutParams = layout;
  }

  get layoutParams() {
    return this.m_layoutParams;
  }

  set originalPixelSize(size) {
    if (!this.m_widgetOriginalPixelSize.eq(size)) {
      this.m_widgetOriginalPixelSize = size;
      this.m_originalPixelSizeDirty = true;
    }
  }

  get originalPixelSize() {
    return this.m_widgetOriginalPixelSize;
  }

  set originalSize(size) {
    if (!this.m_widgetOriginalSize.eq(size)) {
      this.m_widgetOriginalSize = size;
    }
  }

  get originalSize() {
    return this.m_widgetOriginalSize;
  }

  getTextureNormalizedScale() {
    const normalizedScale = new Vec2$2(0, 0);

    if (this.m_normalizedSize.x < 0 || this.m_normalizedSize.y < 0 || this.m_widgetOriginalSize.x <= 0 || this.m_widgetOriginalSize.y <= 0) {
      return normalizedScale;
    }

    normalizedScale.x = this.m_normalizedSize.x / this.m_widgetOriginalSize.x;
    normalizedScale.y = this.m_normalizedSize.y / this.m_widgetOriginalSize.y;
    return normalizedScale;
  }

  updateOriginaSize(size, screenSize) {
    this.m_widgetOriginalPixelSize = size;
    this.m_widgetOriginalSize.x = size.x / screenSize.x * 2;
    this.m_widgetOriginalSize.y = size.y / screenSize.y * 2;
  }

  setAnimationParameters(animation_arr) {
    if (animation_arr && animation_arr instanceof Array) {
      animation_arr.forEach(value => {
        if (null != value) {
          const animParam = TemplateConfigParser.parseAnimationConfig(value);
          if ((animParam === null || animParam === void 0 ? void 0 : animParam.anim_type) == null) return;
          const animation_type = AnimationType[animParam === null || animParam === void 0 ? void 0 : animParam.anim_type];

          if (animation_type != null) {
            this.setWidgetAnimation(animParam.anim_resource_path, animParam.anim_resource_id, animParam.anim_script_type, animParam.anim_start_time, animParam.duration, animParam.loop_duration, animation_type);
          } else {
            console.error(TEMPLATE_TAG, 'widget setAnimationParameters error, has no anim_type in json');
          }
        }
      });
    }
  }

  setParameters(jsonParam) {
    // TODO: need set UI Constained and animation
    if (jsonParam) {
      super.parameters = jsonParam; // for UI Constained

      if ('layout_params' in jsonParam) {
        const layoutParamConfig = jsonParam.layout_params;
        this.layoutParams = layoutParamConfig;
      }

      if ('original_size' in jsonParam) {
        const widgetPixelSize = AmazUtils$1.CastJsonArray2fToAmazVector2f(jsonParam.original_size);

        if (widgetPixelSize) {
          this.originalPixelSize = widgetPixelSize;
        } else {
          console.error(TEMPLATE_TAG, 'original_size in json is not vector2f:', JSON.stringify(jsonParam.original_size));
        }
      }

      if ('anims' in jsonParam) {
        // for animation parameters
        const animation_arr = jsonParam.anims;
        this.setAnimationParameters(animation_arr);
      }
    }
  }

  getParameters() {
    const widget2DAnims = [];

    if (this.m_animations) {
      this.m_animations.forEach((anima, key) => {
        if (anima) {
          const anima_typestr = AnimationType[key];
          const animaScriptType = anima.animationScriptType === ScriptType.LUA ? 'lua' : 'js';
          const animation = {
            anim_type: anima_typestr,
            anim_script_type: animaScriptType,
            anim_resource_id: anima.animationResourceID,
            anim_resource_path: anima.animationPath,
            anim_start_time: anima.animationStartTime,
            duration: anima.animationDuration,
            loop_duration: anima.m_animationLoopDuration
          };
          widget2DAnims.push(animation);
        }
      });
    }

    const widget2DParam = {
      original_size: [this.originalPixelSize.x, this.originalPixelSize.y],
      layout_params: this.layoutParams,
      anims: widget2DAnims
    };
    return widget2DParam;
  }

  setWidgetAnimation(path, resourceID, scriptType, startTime, duration, loopDuration, animType) {
    var _a, _b, _c;

    if (((_a = this.m_animations) === null || _a === void 0 ? void 0 : _a.has(animType)) && ((_c = (_b = this.m_animations) === null || _b === void 0 ? void 0 : _b.get(animType)) === null || _c === void 0 ? void 0 : _c.animationPath) === path) {
      // update states
      this.updateWidgetAnimation(startTime, duration, loopDuration, animType);
    } else {
      // recreate animation
      this.resetAnimation(animType);

      if (path != null && path != '') {
        this.addWidgetAnimation(path, resourceID, scriptType, startTime, duration, loopDuration, animType);
      }
    } // TODO: update animation time range if animation is overlap on the timeline


    return true;
  }

  updateWidgetAnimation(startTime, duration, loopDuration, animType) {
    var _a;

    const anim = (_a = this.m_animations) === null || _a === void 0 ? void 0 : _a.get(animType);

    if (anim) {
      if (-1 !== startTime) {
        anim.animationStartTime = startTime;
      }

      anim.animationDuration = Math.max(duration, 0);
      anim.animationEndTime = anim.animationStartTime + anim.animationDuration;
      anim.animationLoopDuration = Math.max(loopDuration, 0);
    }
  }

  addWidgetAnimation(path, resourceID, scriptType, startTime, duration, loopDuration, animType) {
    const anim = new Animation2D(path, resourceID, scriptType);
    anim.animationStartTime = startTime;
    anim.animationEndTime = startTime + Math.max(duration, 0);
    anim.animationDuration = Math.max(duration, 0);
    anim.animationLoopDuration = Math.max(loopDuration, 0);
    anim.animationType = animType;

    if (null != this.m_animations) {
      this.m_animations.set(anim.animationType, anim);
    } else {
      this.m_animations = new Map();
      this.m_animations.set(anim.animationType, anim);
    }

    return true;
  }

  resetAnimation(animType) {
    if (null != this.m_animations && this.m_animations.has(animType)) {
      const anim = this.m_animations.get(animType);

      if (anim !== undefined) {
        if (this.m_renderEntity) {
          anim.unloadAnmation(this.m_renderEntity);
          this.m_animations.delete(anim.animationType);
        }
      }
    }
  }

  reloadAllAnimation() {
    var _a;

    (_a = this.m_animations) === null || _a === void 0 ? void 0 : _a.forEach(anim => {
      if (anim !== undefined) {
        if (this.m_renderEntity) {
          anim.reloadAnimation(this.m_renderEntity);

          this._updatePassthroughParams(anim);
        }
      }
    });
  }

  resetAllAnimation() {
    var _a;

    (_a = this.m_animations) === null || _a === void 0 ? void 0 : _a.forEach(anim => {
      if (anim !== undefined) {
        if (this.m_renderEntity) {
          anim.unloadAnmation(this.m_renderEntity);
        }
      }
    });
  } // eslint-disable-next-line @typescript-eslint/no-unused-vars


  onUpdate(_timeStamp) {
    super.onUpdate(_timeStamp);
  }

  _setPassthroughParams(scriptComponent) {
    this.m_scriptPassthroughParams.forEach((value, key) => {
      scriptComponent.properties.set(key, value);
    });
    scriptComponent.properties.set('enable_infosticker_new_text_component', true);
  }

  _updatePassthroughParams(anim) {
    if (null !== anim.m_scriptComponet) {
      this._setPassthroughParams(anim.m_scriptComponet);
    }
  }

  seekAnimations(timestamp) {
    const isInRange = this.compareFloatRange;
    let animTimestamp = timestamp - this.startTime;
    if (animTimestamp < 0) animTimestamp = 0;
    if (!this.m_animations || !this.renderEntity) return; // run onLeave

    let reEnter = false;
    Array.from(this.m_animations).map(([anim_type, anim]) => {
      if (anim && anim_type && !anim.loaded) {
        anim.loadAnimation(anim.animationPath, this.renderEntity);
      }

      if (this.m_scriptPassthroughParamsDirty === true && anim) {
        this._updatePassthroughParams(anim);
      }

      return anim;
    }).map(anim => {
      if (anim) {
        const inAnim = isInRange(anim.animationStartTime, anim.animationEndTime, animTimestamp, true);

        if (!inAnim && anim.state.entered === true) {
          anim.onLeave();

          if (!reEnter) {
            reEnter = true;
            this.resetParams();
          }
        }
      }

      return anim;
    }).map(anim => {
      if (anim) {
        const inAnim = isInRange(anim.animationStartTime, anim.animationEndTime, animTimestamp, true);

        if (inAnim) {
          if (anim.state.entered === false || reEnter) {
            anim.onEnter();
            anim.state.entered = true;
          }

          anim.seek(animTimestamp);
        }
      }
    });
    this.m_scriptPassthroughParamsDirty = false;
  }

  resetParams() {}

  static createRenderEntity(scene, rootEntity, name, layer) {
    const renderEntityName = name;
    const renderEntity = AmazUtils$1.createEntity(renderEntityName, scene);
    renderEntity.layer = layer;
    const localPos = new Vec3$3(0.0, 0.0, 0.0);
    const scale = new Vec3$3(1.0, 1.0, 1.0);
    const rotate = new Vec3$3(0.0, 0.0, 0.0);
    renderEntity.transform = {
      position: localPos,
      scale: scale,
      rotation: rotate
    };
    if (rootEntity) AmazUtils$1.addChildEntity(rootEntity, renderEntity);
    return renderEntity;
  }

  static removeRenderEntity(rootEntity, renderEntity) {
    if (!renderEntity) return false;
    const root = rootEntity;
    if (root) AmazUtils$1.removeChildEntity(root, renderEntity);
    return true;
  }

  get renderEntity() {
    if (!this.m_renderEntity) {
      this.m_renderEntity = Widget2D.createRenderEntity(this.m_scene, this.m_rootEntity, this.m_name + 'renderEntity', this.m_cameraLayer);
    }

    return this.m_renderEntity;
  }

  set renderEntity(entity) {
    if (this.m_renderEntity) {
      Widget2D.removeRenderEntity(this.m_rootEntity, this.m_renderEntity);
      this.m_renderEntity.scene.removeEntity(this.m_renderEntity);
      this.m_renderEntity = null;
    }

    this.m_renderEntity = entity;
  }

  onUpdateAnimationDuration(originTime, newTime) {
    var _a;

    if (this.m_animations == null) return;
    const animTimeRanges = new Map(Array.from(this.m_animations).map(val => {
      const ret = [val[0], new TimeRange(val[1].animationStartTime, val[1].animationDuration)];
      return ret;
    }));
    (_a = this.calculateAnimDuration(originTime, newTime, animTimeRanges)) === null || _a === void 0 ? void 0 : _a.forEach((animTime, type) => {
      if (this.m_animations != null && this.m_animations.has(type)) {
        this.m_animations.get(type).animationStartTime = animTime.startTime;
        this.m_animations.get(type).animationEndTime = animTime.endTime;
      }
    });
  }

  calculateAnimDuration(originTimeRange, newTimeRange, animTimeRanges) {
    const animDuration = Array.from(animTimeRanges).reduce((prev, val) => prev + val[1].duration, 0); // scale

    if (animDuration < originTimeRange.duration && animDuration < newTimeRange.duration && originTimeRange.duration !== 0) {
      const durationScale = newTimeRange.duration / originTimeRange.duration;
      return new Map(Array.from(animTimeRanges).map(val => {
        const ret = [val[0], new TimeRange(val[1].startTime * durationScale, val[1].duration * durationScale)];
        return ret;
      }));
    } // TODO: duration logic


    return undefined;
  }

}

var Amaz$4 = effect.Amaz;
var Vec3$2 = Amaz$4.Vector3f;
var Vec2$1 = Amaz$4.Vector2f;
var Color = Amaz$4.Color;
var ShapeType;

(function (ShapeType) {
  ShapeType[ShapeType["CONTOUR_RECT"] = 0] = "CONTOUR_RECT";
  ShapeType[ShapeType["CONTOUR_ELLIPSE"] = 1] = "CONTOUR_ELLIPSE";
  ShapeType[ShapeType["CONTOUR_STAR"] = 2] = "CONTOUR_STAR";
  ShapeType[ShapeType["CONTOUR_POLYGON"] = 3] = "CONTOUR_POLYGON";
  ShapeType[ShapeType["CUSTOM_CONTOUR_POLYGON"] = 4] = "CUSTOM_CONTOUR_POLYGON";
  ShapeType[ShapeType["LINE"] = 5] = "LINE";
  ShapeType[ShapeType["ARROW"] = 6] = "ARROW";
})(ShapeType || (ShapeType = {}));

var ShapeLineType;

(function (ShapeLineType) {
  ShapeLineType[ShapeLineType["SOLID_LINE"] = 0] = "SOLID_LINE";
  ShapeLineType[ShapeLineType["BROKEN_LINE"] = 1] = "BROKEN_LINE";
  ShapeLineType[ShapeLineType["DOTTED_LINE"] = 2] = "DOTTED_LINE";
})(ShapeLineType || (ShapeLineType = {})); // for inline and out line stroke side type
// those need coustom points be clockwise, which is decided by IFShapeDrawSolidFill


const inlineSideType = Amaz$4.IFShapeStrokeSideType.INSIDE;
const outlineSideType = Amaz$4.IFShapeStrokeSideType.OUTSIDE;
const bothSideType = Amaz$4.IFShapeStrokeSideType.CENTER; //this ratio is for arrow, when lineWidth changed, the arrow line must be changed too. like linwidth is 10, the arrow line distance is 40

const arrowLineWidthRatio = 3.14;
class Shape extends Widget2D {
  constructor(name, widgetType, scene) {
    super(name, widgetType, scene);
    this.m_needUpdateShape = true;
    this.m_shapeParameters = null;
    this.m_shapeCom = null; //this shape blend entity is just for shape

    this.m_shapeBlendEntity = null;
    this.m_shapeBlendMeshRenderer = null;
    this.m_renderRTTexture = null;
    this.m_shapeType = ShapeType.CUSTOM_CONTOUR_POLYGON;
    this.m_globalAlpha = 1.0;
    this.m_pointsNumber = 0;
    this.m_points = [];
    this.m_pointsIn = [];
    this.m_pointsOut = [];
    this.m_arrowPoints = new Amaz$4.Vec2Vector();
    this.m_color = new Color(1.0, 0.0, 0.0, 1.0);
    this.m_roundness = [];
    this.m_shadowEnable = false;
    this.m_shadowColor = new Color(1.0, 0.0, 0.0, 1.0);
    this.m_shadowOffset = new Vec2$1(0.0, 0.0);
    this.m_lineWidth = 21;
    this.m_lineType = ShapeLineType.SOLID_LINE;
    this.m_lineLength = [];
    this.m_lineGap = [];
    this.m_centerlineEnable = false;
    this.m_centerlineColor = new Color(1.0, 0.0, 0.0, 1.0);
    this.m_centerlineWidth = 21;
    this.m_centerlineType = ShapeLineType.SOLID_LINE;
    this.m_centerlineLength = [];
    this.m_centerlineGap = [];
    this.m_outlineEnable = false;
    this.m_outlineColor = new Color(1.0, 0.0, 0.0, 1.0);
    this.m_outlineWidth = 21;
    this.m_outlineType = ShapeLineType.SOLID_LINE;
    this.m_outlineLength = [];
    this.m_outlineGap = [];
    this.m_inlineEnable = false;
    this.m_inlineColor = new Color(1.0, 0.0, 0.0, 1.0);
    this.m_inlineWidth = 21;
    this.m_inlineType = ShapeLineType.SOLID_LINE;
    this.m_inlineLength = [];
    this.m_inlineGap = []; //current shape

    this.m_shapeContourPath = null; // arrow shape make up of a straight line and a broken line

    this.m_shapeCotourPathArrow = null;
    this.m_shapeRoundCorner = null;
    this.m_shapeContourEllipse = null;
    this.m_shapeSolidFill = null;
    this.m_shapeLineStroke = null;
    this.m_shapeArrowSolidFill = null;
    this.m_shapeArrowGroup = null;
    this.m_shapeLineStrokeDash = null; //current shadow

    this.m_shapeShadowContourPath = null; // arrow shape make up of a straight line and a broken line

    this.m_shapeShadowCotourPathArrow = null;
    this.m_shapeShadowContourEllipse = null;
    this.m_shapeShadowSolidFill = null;
    this.m_shapeShadowLineStroke = null;
    this.m_shapeShadowArrowSolidFill = null;
    this.m_shapeShadowArrowGroup = null;
    this.m_shapeShadowLineStrokeDash = null;
    this.m_shadowGroup = null; //centerline

    this.m_centerlineSolidStroke = null;
    this.m_centerlineSolidStrokeDash = null; //inline

    this.m_inlineSolidStroke = null;
    this.m_inlineSolidStrokeDash = null; //outline

    this.m_outlineSolidStroke = null;
    this.m_outlineSolidStrokeDash = null;
    this.m_shapeGroup = null;
  }

  createShape(jsonParam, scene) {
    this._createShapeEntity(scene);

    this._creatShapeBlendEntity(scene);

    this._createShapeGroup(jsonParam);

    this.parameters = jsonParam;
  }

  set parameters(params) {
    super.setParameters(params);
    this.m_shapeParameters = params;

    if (this.m_shapeParameters == null) {
      console.error(TEMPLATE_TAG, 'shape parameter is null');
      return;
    }

    this.m_needUpdateShape = true;
    this.updateRootEntityParam();
    this.updateShapeBlendOrder();
    this.updateShape();
  }

  get parameters() {
    const shapeParams = {
      shape_type: this.shapeType,
      global_alpha: this.globalAlpha,
      custom_points: {
        points_number: this.pointNum,
        custom_roundness: this.shapeRoundness,
        points: this.points,
        points_in: this.pointsIn,
        points_out: this.pointsOut
      },
      color: [this.shapeColor.r, this.shapeColor.g, this.shapeColor.b, this.shapeColor.a],
      lineType: this.lineType,
      lineWidth: this.lineWidth,
      lineLength: this.lineLength,
      lineGap: this.lineGap,
      shadow: this.shadowEnable,
      shadowColor: [this.shadowColor.r, this.shadowColor.g, this.shadowColor.b, this.shadowColor.a],
      shadowOffset: [this.shadowOffset.x, this.shadowOffset.y],
      outline: this.outlineEnable,
      outlineWidth: this.outlineWidth,
      outlineType: this.outlineType,
      outlineLength: this.outlineLength,
      outlineGap: this.outlineGap,
      outlineColor: [this.outlineColor.r, this.outlineColor.g, this.outlineColor.b, this.outlineColor.a],
      inline: this.inlineEnable,
      inlineWidth: this.inlineWidth,
      inlineType: this.inlineType,
      inlineLength: this.inlineLength,
      inlineGap: this.inlineGap,
      inlineColor: [this.inlineColor.r, this.inlineColor.g, this.inlineColor.b, this.inlineColor.a],
      centerline: this.centerlineEnable,
      centerlineType: this.centerlineType,
      centerlineLength: this.centerlineLength,
      centerlineGap: this.centerlineGap,
      centerlineWidth: this.centerlineWidth,
      centerlineColor: [this.centerlineColor.r, this.centerlineColor.g, this.centerlineColor.b, this.centerlineColor.a]
    };
    const widgetParam = super.parameters;
    const widget2DParam = super.getParameters();
    const shapeSegmentParam = {
      name: widgetParam.name,
      type: widgetParam.type,
      position: widgetParam.position,
      rotation: widgetParam.rotation,
      scale: widgetParam.scale,
      order_in_layer: widgetParam.order_in_layer,
      start_time: widgetParam.start_time,
      duration: widgetParam.duration,
      layout_params: widget2DParam.layout_params,
      original_size: widget2DParam.original_size,
      shape_params: shapeParams,
      anims: widget2DParam.anims
    };
    return shapeSegmentParam;
  }

  set shapeType(shape_type) {
    if (shape_type !== this.m_shapeType) {
      this.m_shapeType = shape_type;
    }
  }

  get shapeType() {
    return this.m_shapeType;
  }

  set globalAlpha(alpha) {
    if (alpha !== this.m_globalAlpha) {
      this.m_globalAlpha = alpha; // if (this.m_shapeGroup) {
      //   this.m_shapeGroup.alpha = alpha;
      // }
    }
  }

  get globalAlpha() {
    return this.m_globalAlpha;
  }

  updateShapeBlendOrder() {
    if (this.m_needUpdateShapeBlendOrder) {
      this.m_needUpdateShapeBlendOrder = false;
      const blendOrder = this.m_layer * LAYER_SIZE + this.m_localOrder * ORDER_SIZE + 1;

      if (this.m_shapeBlendMeshRenderer) {
        this.m_shapeBlendMeshRenderer.sortingOrder = blendOrder;
      }
    }
  }

  updateShapeWH() {
    if (this.shapeType !== ShapeType.CUSTOM_CONTOUR_POLYGON) {
      if (this.m_shapeContourEllipse && this.m_shapeShadowContourEllipse) {
        this.m_shapeContourEllipse.size = new Vec2$1(this.originalPixelSize.x, this.originalPixelSize.y);
        this.m_shapeShadowContourEllipse.size = new Vec2$1(this.originalPixelSize.x, this.originalPixelSize.y);
      }
    }
  }

  set pointNum(point_num) {
    if (point_num !== this.m_pointsNumber) {
      this.m_pointsNumber = point_num;
    }
  }

  get pointNum() {
    return this.m_pointsNumber;
  } // for

  /**
                  +----+
                  | P3 |  ++
                  +----++-++-+
                      +-+    +-+
                    +-+        +-+
                  +-+            +-+
      +----+   +-+                +-+
      | P2 | -++                    +-+
      +----+  +-+                     +-+
                +-+                     +-+
                  +-+                     +-+
                    +-+                     +-+
                      +-+                     +-+
                +----+   +|                      +-+
                | P1 |    |                        +-+
                +----+    |                  +----+  +-+
                          |                  | P4 |    +>
                          |                  +----+  +-+
                +----+    |                        +-+
                | P7 |    |                      +-+
                +----+  +-v                    +-+
                      +-+                    +-+
                    +-+                    +-+
                  +-+                    +-+
                +-+                    +-+
      +----+  +-+                    +-+
      | P6 |-++                    +-+
      +----+ +-+                 +-+
              +-+             +-+
                +-+         +-+
                  +-+     +-+
              +----++-+ +-+
              | P5 |  +>+
              +----+
  */


  calculateArrowPoints(points) {
    const arrow = new Vec2$1(points[0] - points[2], points[1] - points[3]);
    this.m_arrowPoints.clear();

    if (arrow.x === 0 && arrow.y === 0) {
      return;
    }

    const arrowEnd = new Vec2$1(points[0], points[1]);
    const arrowDir = arrow.normalizeFast();
    const arrowLDir = new Vec2$1(-arrowDir.y, arrowDir.x);
    const arrowRDir = new Vec2$1(arrowDir.y, -arrowDir.x);
    const P1 = Vec2$1.add(arrowEnd, Vec2$1.mul(arrowLDir, this.lineWidth * 0.5));
    const P7 = Vec2$1.add(arrowEnd, Vec2$1.mul(arrowRDir, this.lineWidth * 0.5));
    const P4 = Vec2$1.add(arrowEnd, Vec2$1.mul(arrowDir, this.lineWidth * (0.5 + Math.sqrt(2))));
    const arrowLBDir = Vec2$1.div(Vec2$1.sub(arrowLDir, arrowDir), Math.sqrt(2));
    const arrowRBDir = Vec2$1.div(Vec2$1.sub(arrowRDir, arrowDir), Math.sqrt(2));
    const P2 = Vec2$1.add(P1, Vec2$1.mul(arrowLBDir, this.lineWidth * (arrowLineWidthRatio - 0.5 - Math.sqrt(2) * 0.5)));
    const P6 = Vec2$1.add(P7, Vec2$1.mul(arrowRBDir, this.lineWidth * (arrowLineWidthRatio - 0.5 - Math.sqrt(2) * 0.5)));
    const P3 = Vec2$1.add(P4, Vec2$1.mul(arrowLBDir, this.lineWidth * (arrowLineWidthRatio + 0.5)));
    const P5 = Vec2$1.add(P4, Vec2$1.mul(arrowRBDir, this.lineWidth * (arrowLineWidthRatio + 0.5)));
    this.m_arrowPoints.pushBack(P1);
    this.m_arrowPoints.pushBack(P2);
    this.m_arrowPoints.pushBack(P3);
    this.m_arrowPoints.pushBack(P4);
    this.m_arrowPoints.pushBack(P5);
    this.m_arrowPoints.pushBack(P6);
    this.m_arrowPoints.pushBack(P7);
  }

  updateShapeArrowPath() {
    if (this.m_shapeCotourPathArrow && this.m_shapeShadowCotourPathArrow && this.m_points.length === 4) {
      // for arrow shape, there use one line and one fill shape to draw. base line is passed by user, the filled shape is calculate by calculateArrowPoints function
      this.calculateArrowPoints(this.m_points);
      this.m_shapeCotourPathArrow.pathPoints = this.m_arrowPoints;
      const shadowPointVec = new Amaz$4.Vec2Vector();
      const arrowPointsVec = new Amaz$4.Vec2Vector();
      const pathInPoint = new Vec2$1(0, 0);

      for (let i = 0; i < this.m_arrowPoints.size(); i++) {
        const shadowPoint = Vec2$1.add(this.m_arrowPoints.get(i), this.shadowOffset);
        shadowPointVec.pushBack(shadowPoint);
        arrowPointsVec.pushBack(pathInPoint);
      }

      this.m_shapeCotourPathArrow.pathInDirs = arrowPointsVec;
      this.m_shapeCotourPathArrow.pathOutDirs = arrowPointsVec;
      this.m_shapeShadowCotourPathArrow.pathPoints = shadowPointVec;
      this.m_shapeShadowCotourPathArrow.pathInDirs = arrowPointsVec;
      this.m_shapeShadowCotourPathArrow.pathOutDirs = arrowPointsVec;
    }
  }

  set points(points) {
    this.m_points = points;
    const shadowOffset = this.shadowOffset;

    if (this.shapeType === ShapeType.CUSTOM_CONTOUR_POLYGON || this.shapeType === ShapeType.LINE || this.shapeType === ShapeType.ARROW) {
      if (this.pointNum === this.m_points.length / 2) {
        const pointsVec2 = new Amaz$4.Vec2Vector();
        const shadowPoints = new Amaz$4.Vec2Vector(); // for test modify

        for (let i = 0; i < this.pointNum; i++) {
          const point = new Vec2$1(this.m_points[2 * i], this.m_points[2 * i + 1]);
          const shadow_point = new Vec2$1(this.m_points[2 * i] + shadowOffset.x, this.m_points[2 * i + 1] + shadowOffset.y);
          pointsVec2.pushBack(point);
          shadowPoints.pushBack(shadow_point);
        }

        if (this.m_shapeContourPath && this.m_shapeShadowContourPath) {
          this.m_shapeContourPath.pathPoints = pointsVec2;
          this.m_shapeShadowContourPath.pathPoints = shadowPoints;
        } // for arrow path update


        this.updateShapeArrowPath();
      } else {
        console.error(TEMPLATE_TAG, 'shape points array not match point number!');
      }
    }
  }

  get points() {
    return this.m_points;
  }

  set pointsIn(points_in) {
    this.m_pointsIn = points_in;

    if (this.shapeType === ShapeType.CUSTOM_CONTOUR_POLYGON || this.shapeType === ShapeType.LINE || this.shapeType === ShapeType.ARROW) {
      if (this.pointNum === this.m_pointsIn.length / 2) {
        const pointsIn = new Amaz$4.Vec2Vector();
        const shadow_points_in = new Amaz$4.Vec2Vector();

        for (let i = 0; i < this.pointNum; i++) {
          const point = new Vec2$1(this.m_pointsIn[2 * i], this.m_pointsIn[2 * i + 1]);
          pointsIn.pushBack(point);
          shadow_points_in.pushBack(point);
        }

        if (this.m_shapeContourPath && this.m_shapeShadowContourPath) {
          this.m_shapeContourPath.pathInDirs = pointsIn;
          this.m_shapeShadowContourPath.pathInDirs = shadow_points_in;
        } // for arrow the arrow up and down line don't need points in or out control points.

      } else {
        console.error(TEMPLATE_TAG, 'shape points in array not match point number!');
      }
    }
  }

  get pointsIn() {
    return this.m_pointsIn;
  }

  set pointsOut(points_out) {
    this.m_pointsOut = points_out;

    if (this.shapeType === ShapeType.CUSTOM_CONTOUR_POLYGON || this.shapeType === ShapeType.LINE || this.shapeType === ShapeType.ARROW) {
      if (this.pointNum === this.m_pointsOut.length / 2) {
        const pointsOut = new Amaz$4.Vec2Vector();
        const shadow_points_out = new Amaz$4.Vec2Vector();

        for (let i = 0; i < this.pointNum; i++) {
          const point = new Vec2$1(this.m_pointsOut[2 * i], this.m_pointsOut[2 * i + 1]);
          pointsOut.pushBack(point);
          shadow_points_out.pushBack(point);
        }

        if (this.m_shapeContourPath && this.m_shapeShadowContourPath) {
          this.m_shapeContourPath.pathOutDirs = pointsOut;
          this.m_shapeShadowContourPath.pathOutDirs = shadow_points_out;
        } // for arrow the arrow up and down line don't need points in or out control points.

      } else {
        console.error(TEMPLATE_TAG, 'shape points out array not match point number!');
      }
    }
  }

  get pointsOut() {
    return this.m_pointsOut;
  }

  set shapeColor(color) {
    if (!this.m_color.eq(color)) {
      this.m_color = color; // set custom shape and ellipse shape color

      if (this.m_shapeSolidFill) {
        this.m_shapeSolidFill.color = color;
      } // set line and arrow straight shape color


      if (this.m_shapeLineStroke) {
        this.m_shapeLineStroke.color = color;
      } //set arrow broken line color


      if (this.m_shapeArrowSolidFill) {
        this.m_shapeArrowSolidFill.color = color;
      }
    }
  }

  get shapeColor() {
    return this.m_color;
  }

  set shapeRoundness(roundness) {
    this.m_roundness = roundness;

    if (this.m_shapeRoundCorner) {
      const roundessArr = new Amaz$4.FloatVector();

      for (let i = 0; i < roundness.length; i++) {
        roundessArr.pushBack(roundness[i]);
      }

      this.m_shapeRoundCorner.radius = roundessArr;
    }
  }

  get shapeRoundness() {
    return this.m_roundness;
  }

  updateShapeLineDash(width) {
    // for dotted line  stroke dash need a offset to make arrow draw don't overlap
    if (this.lineType === ShapeLineType.DOTTED_LINE) {
      if (this.m_shapeLineStrokeDash) {
        this.m_shapeLineStrokeDash.offset = -0.5 * width;
      }

      if (this.m_shapeShadowLineStrokeDash) {
        this.m_shapeShadowLineStrokeDash.offset = -0.5 * width;
      }
    } else {
      if (this.m_shapeLineStrokeDash) {
        this.m_shapeLineStrokeDash.offset = 0;
      }

      if (this.m_shapeShadowLineStrokeDash) {
        this.m_shapeShadowLineStrokeDash.offset = 0;
      }
    }
  }

  set lineWidth(width) {
    if (this.m_lineWidth !== width) {
      this.m_lineWidth = width; //set line or arrow line width

      if (this.m_shapeLineStroke) {
        this.m_shapeLineStroke.width = width;
      } // set line or arrow line shadow width


      if (this.m_shapeShadowLineStroke) {
        this.m_shapeShadowLineStroke.width = width;
      } // for dotted line  stroke dash need a offset to make arrow draw don't overlap


      this.updateShapeLineDash(width);
    }
  }

  get lineWidth() {
    return this.m_lineWidth;
  }

  set shadowEnable(enable) {
    if (this.m_shadowEnable !== enable) {
      this.m_shadowEnable = enable;

      if (this.m_shadowGroup) {
        this.m_shadowGroup.enable = enable;
      }
    }
  }

  get shadowEnable() {
    return this.m_shadowEnable;
  }

  set shadowColor(color) {
    if (!this.m_shadowColor.eq(color)) {
      this.m_shadowColor = color; // set custom shape and ellipse shadow color

      if (this.m_shapeShadowSolidFill) {
        this.m_shapeShadowSolidFill.color = color;
      } //set line and arrow shadow color


      if (this.m_shapeShadowLineStroke) {
        this.m_shapeShadowLineStroke.color = color;
      }

      if (this.m_shapeShadowArrowSolidFill) {
        this.m_shapeShadowArrowSolidFill.color = color;
      }
    }
  }

  get shadowColor() {
    return this.m_shadowColor;
  }

  set shadowOffset(offset) {
    if (!this.m_shadowOffset.eq(offset)) {
      this.m_shadowOffset = offset;

      if ((this.shapeType === ShapeType.CUSTOM_CONTOUR_POLYGON || this.shapeType === ShapeType.LINE || this.shapeType === ShapeType.ARROW) && this.m_shapeShadowContourPath) {
        const shadowPoints = new Amaz$4.Vec2Vector();

        for (let i = 0; i < this.pointNum; i++) {
          const shadow_point = new Vec2$1(this.points[2 * i] + offset.x, this.points[2 * i + 1] + offset.y);
          shadowPoints.pushBack(shadow_point);
        }

        this.m_shapeShadowContourPath.pathPoints = shadowPoints;

        if (this.shapeType === ShapeType.ARROW && this.m_shapeShadowCotourPathArrow) {
          const shadowArrowPoints = new Amaz$4.Vec2Vector();

          for (let i = 0; i < this.m_arrowPoints.size(); i++) {
            const shadowPoint = Vec2$1.add(this.m_arrowPoints.get(i), offset);
            shadowArrowPoints.pushBack(shadowPoint);
          }

          this.m_shapeShadowCotourPathArrow.pathPoints = shadowArrowPoints;
        }
      } else if (this.shapeType === ShapeType.CONTOUR_ELLIPSE && this.m_shapeShadowContourEllipse) {
        this.m_shapeShadowContourEllipse.position = offset;
      }
    }
  }

  get shadowOffset() {
    return this.m_shadowOffset;
  }

  set lineType(lineType) {
    if (this.m_lineType !== lineType) {
      this.m_lineType = lineType;

      if (lineType === ShapeLineType.DOTTED_LINE) {
        if (this.m_shapeLineStroke) {
          this.m_shapeLineStroke.capType = Amaz$4.IFShapeStrokeCapType.ROUND;
        }

        if (this.m_shapeShadowLineStroke) {
          this.m_shapeShadowLineStroke.capType = Amaz$4.IFShapeStrokeCapType.ROUND;
          const len = this.m_centerlineLength.length;

          for (let i = 0; i < len; i++) {
            this.m_centerlineLength[i] = 0.0;
          }
        }
      } else {
        if (lineType === ShapeLineType.SOLID_LINE) {
          this.lineLength = [];
          this.lineGap = [];
        }

        if (this.m_shapeLineStroke) {
          this.m_shapeLineStroke.capType = Amaz$4.IFShapeStrokeCapType.FLAT;
        }

        if (this.m_shapeShadowLineStroke) {
          this.m_shapeShadowLineStroke.capType = Amaz$4.IFShapeStrokeCapType.FLAT;
        }
      } // for dotted line  stroke dash need a offset to make arrow draw don't overlap


      this.updateShapeLineDash(this.lineWidth);
    }
  }

  get lineType() {
    return this.m_lineType;
  }

  set lineLength(length) {
    this.m_lineLength = length;

    if (this.lineType === ShapeLineType.SOLID_LINE) {
      this.m_lineLength = [];
    } else if (this.lineType === ShapeLineType.DOTTED_LINE) {
      const len = this.m_lineLength.length;

      for (let i = 0; i < len; i++) {
        this.m_lineLength[i] = 0.0;
      }
    }

    if (this.m_shapeLineStrokeDash && this.m_shapeShadowLineStrokeDash) {
      const lengthArr = new Amaz$4.FloatVector();
      const arrSize = this.m_lineLength.length;

      for (let i = 0; i < arrSize; i++) {
        lengthArr.pushBack(this.m_lineLength[i]);
      }

      this.m_shapeLineStrokeDash.lenth = lengthArr;
      this.m_shapeShadowLineStrokeDash.lenth = lengthArr;
    }
  }

  get lineLength() {
    return this.m_lineLength;
  }

  set lineGap(gap) {
    this.m_lineGap = gap;

    if (this.lineType === ShapeLineType.SOLID_LINE) {
      this.m_lineGap = [];
    }

    if (this.m_shapeLineStrokeDash && this.m_shapeShadowLineStrokeDash) {
      const gapArr = new Amaz$4.FloatVector();
      const arrSize = this.m_lineGap.length;

      for (let i = 0; i < arrSize; i++) {
        gapArr.pushBack(this.m_lineGap[i]);
      }

      this.m_shapeLineStrokeDash.gap = gapArr;
      this.m_shapeShadowLineStrokeDash.gap = gapArr;
    }
  }

  get lineGap() {
    return this.m_lineGap;
  }

  set centerlineEnable(enable) {
    if (this.m_centerlineEnable !== enable) {
      this.m_centerlineEnable = enable;

      if (this.m_centerlineSolidStroke) {
        this.m_centerlineSolidStroke.enable = enable;
      }
    }
  }

  get centerlineEnable() {
    return this.m_centerlineEnable;
  }

  set centerlineType(lineType) {
    if (this.m_centerlineType !== lineType) {
      this.m_centerlineType = lineType;

      if (this.m_centerlineSolidStroke) {
        if (lineType === ShapeLineType.DOTTED_LINE) {
          this.m_centerlineSolidStroke.capType = Amaz$4.IFShapeStrokeCapType.ROUND;
          const len = this.m_centerlineLength.length;

          for (let i = 0; i < len; i++) {
            this.m_centerlineLength[i] = 0.0;
          }
        } else {
          if (lineType === ShapeLineType.SOLID_LINE) {
            this.centerlineLength = [];
            this.centerlineGap = [];
          }

          this.m_centerlineSolidStroke.capType = Amaz$4.IFShapeStrokeCapType.FLAT;
        }
      }
    }
  }

  get centerlineType() {
    return this.m_centerlineType;
  }

  set centerlineLength(length) {
    this.m_centerlineLength = length; // if line type is solid line,then clear length array.

    if (this.centerlineType === ShapeLineType.SOLID_LINE) {
      this.m_centerlineLength = [];
    } else if (this.centerlineType === ShapeLineType.DOTTED_LINE) {
      const len = this.m_centerlineLength.length;

      for (let i = 0; i < len; i++) {
        this.m_centerlineLength[i] = 0.0;
      }
    }

    if (this.m_centerlineSolidStrokeDash) {
      const lenghtArr = new Amaz$4.FloatVector();
      const arraySize = this.m_centerlineLength.length;

      for (let i = 0; i < arraySize; i++) {
        lenghtArr.pushBack(this.m_centerlineLength[i]);
      }

      this.m_centerlineSolidStrokeDash.lenth = lenghtArr;
    }
  }

  get centerlineLength() {
    return this.m_centerlineLength;
  }

  set centerlineGap(gap) {
    this.m_centerlineGap = gap; // if line type is solid line,then clear gap array.

    if (this.centerlineType === ShapeLineType.SOLID_LINE) {
      this.m_centerlineGap = [];
    }

    if (this.m_centerlineSolidStrokeDash) {
      const gapArr = new Amaz$4.FloatVector();
      const arraySize = this.m_centerlineGap.length;

      for (let i = 0; i < arraySize; i++) {
        gapArr.pushBack(this.m_centerlineGap[i]);
      }

      this.m_centerlineSolidStrokeDash.gap = gapArr;
    }
  }

  get centerlineGap() {
    return this.m_centerlineGap;
  }

  set centerlineColor(color) {
    if (!this.m_centerlineColor.eq(color)) {
      this.m_centerlineColor = color;

      if (this.m_centerlineSolidStroke) {
        this.m_centerlineSolidStroke.color = color;
      }
    }
  }

  get centerlineColor() {
    return this.m_centerlineColor;
  }

  set centerlineWidth(width) {
    if (this.m_centerlineWidth !== width) {
      this.m_centerlineWidth = width;

      if (this.m_centerlineSolidStroke) {
        this.m_centerlineSolidStroke.width = width;
      }
    }
  }

  get centerlineWidth() {
    return this.m_centerlineWidth;
  }

  set outlineEnable(enable) {
    if (this.m_outlineEnable !== enable) {
      this.m_outlineEnable = enable;

      if (this.m_outlineSolidStroke) {
        this.m_outlineSolidStroke.enable = enable;
      }
    }
  }

  get outlineEnable() {
    return this.m_outlineEnable;
  }

  set outlineType(lineType) {
    if (this.m_outlineType !== lineType) {
      this.m_outlineType = lineType;

      if (this.m_outlineSolidStroke) {
        if (lineType === ShapeLineType.DOTTED_LINE) {
          this.m_outlineSolidStroke.capType = Amaz$4.IFShapeStrokeCapType.ROUND;
          const len = this.m_centerlineLength.length;

          for (let i = 0; i < len; i++) {
            this.m_centerlineLength[i] = 0.0;
          }
        } else {
          if (lineType === ShapeLineType.SOLID_LINE) {
            this.outlineLength = [];
            this.outlineGap = [];
          }

          this.m_outlineSolidStroke.capType = Amaz$4.IFShapeStrokeCapType.FLAT;
        }
      }
    }
  }

  get outlineType() {
    return this.m_outlineType;
  }

  set outlineLength(length) {
    this.m_outlineLength = length; // if line type is solid line,then clear length array.

    if (this.outlineType === ShapeLineType.SOLID_LINE) {
      this.m_outlineLength = [];
    } else if (this.outlineType === ShapeLineType.DOTTED_LINE) {
      const len = this.m_outlineLength.length;

      for (let i = 0; i < len; i++) {
        this.m_outlineLength[i] = 0.0;
      }
    }

    if (this.m_outlineSolidStrokeDash) {
      const lenghtArr = new Amaz$4.FloatVector();
      const arraySize = this.m_outlineLength.length;

      for (let i = 0; i < arraySize; i++) {
        lenghtArr.pushBack(this.m_outlineLength[i]);
      }

      this.m_outlineSolidStrokeDash.lenth = lenghtArr;
    }
  }

  get outlineLength() {
    return this.m_outlineLength;
  }

  set outlineGap(gap) {
    this.m_outlineGap = gap; // if line type is solid line,then clear gap array.

    if (this.outlineType === ShapeLineType.SOLID_LINE) {
      this.m_outlineGap = [];
    }

    if (this.m_outlineSolidStrokeDash) {
      const gapArr = new Amaz$4.FloatVector();
      const arraySize = this.m_outlineGap.length;

      for (let i = 0; i < arraySize; i++) {
        gapArr.pushBack(this.m_outlineGap[i]);
      }

      this.m_outlineSolidStrokeDash.gap = gapArr;
    }
  }

  get outlineGap() {
    return this.m_outlineGap;
  }

  set outlineColor(color) {
    if (!this.m_outlineColor.eq(color)) {
      this.m_outlineColor = color;

      if (this.m_outlineSolidStroke) {
        this.m_outlineSolidStroke.color = color;
      }
    }
  }

  get outlineColor() {
    return this.m_outlineColor;
  }

  set outlineWidth(width) {
    if (this.m_outlineWidth !== width) {
      this.m_outlineWidth = width;

      if (this.m_outlineSolidStroke) {
        this.m_outlineSolidStroke.width = width;
      }
    }
  }

  get outlineWidth() {
    return this.m_outlineWidth;
  }

  set inlineEnable(enable) {
    if (this.m_inlineEnable !== enable) {
      this.m_inlineEnable = enable;

      if (this.m_inlineSolidStroke) {
        this.m_inlineSolidStroke.enable = enable;
      }
    }
  }

  get inlineEnable() {
    return this.m_inlineEnable;
  }

  set inlineType(lineType) {
    if (this.m_inlineType !== lineType) {
      this.m_inlineType = lineType;

      if (this.m_inlineSolidStroke) {
        if (lineType === ShapeLineType.DOTTED_LINE) {
          this.m_inlineSolidStroke.capType = Amaz$4.IFShapeStrokeCapType.ROUND;
          const len = this.m_centerlineLength.length;

          for (let i = 0; i < len; i++) {
            this.m_centerlineLength[i] = 0.0;
          }
        } else {
          if (lineType === ShapeLineType.SOLID_LINE) {
            this.inlineLength = [];
            this.inlineGap = [];
          }

          this.m_inlineSolidStroke.capType = Amaz$4.IFShapeStrokeCapType.FLAT;
        }
      }
    }
  }

  get inlineType() {
    return this.m_inlineType;
  }

  set inlineLength(length) {
    this.m_inlineLength = length; // if line type is solid line,then clear lenght array.

    if (this.inlineType === ShapeLineType.SOLID_LINE) {
      this.m_inlineLength = [];
    } else if (this.inlineType === ShapeLineType.DOTTED_LINE) {
      const len = this.m_inlineLength.length;

      for (let i = 0; i < len; i++) {
        this.m_inlineLength[i] = 0.0;
      }
    }

    if (this.m_inlineSolidStrokeDash) {
      const lenghtArr = new Amaz$4.FloatVector();
      const arraySize = this.m_inlineLength.length;

      for (let i = 0; i < arraySize; i++) {
        lenghtArr.pushBack(this.m_inlineLength[i]);
      }

      this.m_inlineSolidStrokeDash.lenth = lenghtArr;
    }
  }

  get inlineLength() {
    return this.m_inlineLength;
  }

  set inlineGap(gap) {
    this.m_inlineGap = gap; // if line type is solid line,then clear gap array.

    if (this.inlineType === ShapeLineType.SOLID_LINE) {
      this.m_inlineGap = [];
    }

    if (this.m_inlineSolidStrokeDash) {
      const gapArr = new Amaz$4.FloatVector();
      const arraySize = this.m_inlineGap.length;

      for (let i = 0; i < arraySize; i++) {
        gapArr.pushBack(this.m_inlineGap[i]);
      }

      this.m_inlineSolidStrokeDash.gap = gapArr;
    }
  }

  get inlineGap() {
    return this.m_inlineGap;
  }

  set inlineColor(color) {
    if (!this.m_inlineColor.eq(color)) {
      this.m_inlineColor = color;

      if (this.m_inlineSolidStroke) {
        this.m_inlineSolidStroke.color = color;
      }
    }
  }

  get inlineColor() {
    return this.m_inlineColor;
  }

  set inlineWidth(width) {
    if (this.m_inlineWidth !== width) {
      this.m_inlineWidth = width;

      if (this.m_inlineSolidStroke) {
        this.m_inlineSolidStroke.width = width;
      }
    }
  }

  get inlineWidth() {
    return this.m_inlineWidth;
  }

  _updateShapeBaseParameters(jsonParam) {
    if ('global_alpha' in jsonParam) {
      const alpha = jsonParam.global_alpha;
      this.globalAlpha = alpha;
    }

    if ('color' in jsonParam) {
      const color = AmazUtils$1.CastJsonArray4fToColor(jsonParam.color);

      if (null !== color) {
        this.shapeColor = color;
      } else {
        console.error(TEMPLATE_TAG, 'shape color json error:', JSON.stringify(jsonParam.color));
      }
    }

    if ('lineWidth' in jsonParam) {
      const lineWidthVal = jsonParam.lineWidth;
      this.lineWidth = lineWidthVal;
    }

    if ('lineType' in jsonParam) {
      const lineType = jsonParam.lineType;
      this.lineType = lineType;
    }

    if ('lineLength' in jsonParam) {
      const lineLengthArr = jsonParam.lineLength;
      this.lineLength = lineLengthArr;
    }

    if ('lineGap' in jsonParam) {
      const lineGapArr = jsonParam.lineGap;
      this.lineGap = lineGapArr;
    }
  }

  _updateShapeCustomPoints(jsonParam) {
    if ('custom_points' in jsonParam) {
      const configCustomPoints = jsonParam.custom_points;

      if (configCustomPoints) {
        let pointsNumber = this.pointNum;

        if ('points_number' in configCustomPoints) {
          pointsNumber = configCustomPoints.points_number;
          this.pointNum = pointsNumber;
        }

        if ('points' in configCustomPoints) {
          const pointArray = configCustomPoints.points;
          const pointCount = pointArray.length / 2;

          if (pointCount === pointsNumber) {
            this.points = pointArray;
          } else {
            console.error(TEMPLATE_TAG, 'create custom points shape group: points number is not match the points array:', JSON.stringify(configCustomPoints.points));
            return false;
          }
        }

        if ('points_in' in configCustomPoints) {
          const pointInArray = configCustomPoints.points_in;
          const pointCount = pointInArray.length / 2;

          if (pointCount === pointsNumber) {
            this.pointsIn = pointInArray;
          } else {
            console.error(TEMPLATE_TAG, 'create custom points shape group: points number is not match the points_in array:', JSON.stringify(configCustomPoints.points_in));
            return false;
          }
        }

        if ('points_out' in configCustomPoints) {
          const pointOutArray = configCustomPoints.points_out;
          const pointCount = pointOutArray.length / 2;

          if (pointCount === pointsNumber) {
            this.pointsOut = pointOutArray;
          } else {
            console.error(TEMPLATE_TAG, 'create custom points shape group: points number is not match the points_out array:', JSON.stringify(configCustomPoints.points_out));
            return false;
          }
        }

        if ('custom_roundness' in configCustomPoints) {
          const roundness = configCustomPoints.custom_roundness;
          const roundnessCount = roundness.length;

          if (pointsNumber === roundnessCount) {
            this.shapeRoundness = roundness;
          } else {
            console.error(TEMPLATE_TAG, 'create custom points shape group: points number is not match the roundness array:', JSON.stringify(configCustomPoints.roundness));
          }
        }
      }
    }

    return true;
  }

  _updateShapeCenterline(jsonParam) {
    if ('centerline' in jsonParam) {
      const centerlineEnable = jsonParam.centerline;
      this.centerlineEnable = centerlineEnable;
    }

    if ('centerlineType' in jsonParam) {
      const centerlineType = jsonParam.centerlineType;
      this.centerlineType = centerlineType;
    }

    if ('centerlineLength' in jsonParam) {
      const lineLengthArr = jsonParam.centerlineLength;
      this.centerlineLength = lineLengthArr;
    }

    if ('centerlineGap' in jsonParam) {
      const lineGapArr = jsonParam.centerlineGap;
      this.centerlineGap = lineGapArr;
    }

    if ('centerlineWidth' in jsonParam) {
      const centerlineWidth = jsonParam.centerlineWidth;
      this.centerlineWidth = centerlineWidth;
    }

    if ('centerlineColor' in jsonParam) {
      const centerlineColor = AmazUtils$1.CastJsonArray4fToColor(jsonParam.centerlineColor);

      if (null !== centerlineColor) {
        this.centerlineColor = centerlineColor;
      } else {
        console.error(TEMPLATE_TAG, 'shape outline color json error:', JSON.stringify(jsonParam.centerlineColor));
      }
    }
  }

  _updateShapeOutline(jsonParam) {
    if ('outline' in jsonParam) {
      const outlineEnable = jsonParam.outline;
      this.outlineEnable = outlineEnable;
    }

    if ('outlineType' in jsonParam) {
      const outlineType = jsonParam.outlineType;
      this.outlineType = outlineType;
    }

    if ('outlineLength' in jsonParam) {
      const lineLengthArr = jsonParam.outlineLength;
      this.outlineLength = lineLengthArr;
    }

    if ('outlineGap' in jsonParam) {
      const lineGapArr = jsonParam.outlineGap;
      this.outlineGap = lineGapArr;
    }

    if ('outlineWidth' in jsonParam) {
      const outlineWidth = jsonParam.outlineWidth;
      this.outlineWidth = outlineWidth;
    }

    if ('outlineColor' in jsonParam) {
      const outlineColor = AmazUtils$1.CastJsonArray4fToColor(jsonParam.outlineColor);

      if (null !== outlineColor) {
        this.outlineColor = outlineColor;
      } else {
        console.error(TEMPLATE_TAG, 'shape outline color json error:', JSON.stringify(jsonParam.outlineColor));
      }
    }
  }

  _updateShapeInline(jsonParam) {
    if ('inline' in jsonParam) {
      const inlineEnable = jsonParam.inline;
      this.inlineEnable = inlineEnable;
    }

    if ('inlineType' in jsonParam) {
      const inlineType = jsonParam.inlineType;
      this.inlineType = inlineType;
    }

    if ('inlineLength' in jsonParam) {
      const lineLengthArr = jsonParam.inlineLength;
      this.inlineLength = lineLengthArr;
    }

    if ('inlineGap' in jsonParam) {
      const lineGapArr = jsonParam.inlineGap;
      this.inlineGap = lineGapArr;
    }

    if ('inlineWidth' in jsonParam) {
      const inlineWidth = jsonParam.inlineWidth;
      this.inlineWidth = inlineWidth;
    }

    if ('inlineColor' in jsonParam) {
      const inlineColor = AmazUtils$1.CastJsonArray4fToColor(jsonParam.inlineColor);

      if (null !== inlineColor) {
        this.inlineColor = inlineColor;
      } else {
        console.error(TEMPLATE_TAG, 'shape inline color json error:', JSON.stringify(jsonParam.inlineColor));
      }
    }
  }

  _updateShapeShadow(jsonParam) {
    if ('shadow' in jsonParam) {
      const shadowEnable = jsonParam.shadow;
      this.shadowEnable = shadowEnable;
    }

    if ('shadowColor' in jsonParam) {
      const shadowColor = AmazUtils$1.CastJsonArray4fToColor(jsonParam.shadowColor);

      if (null != shadowColor) {
        this.shadowColor = shadowColor;
      } else {
        console.error(TEMPLATE_TAG, 'shape shadow color json error:', JSON.stringify(jsonParam.shadowColor));
      }
    }

    if ('shadowOffset' in jsonParam) {
      const shadowOffset = AmazUtils$1.CastJsonArray2fToAmazVector2f(jsonParam.shadowOffset);

      if (null != shadowOffset) {
        this.shadowOffset = shadowOffset;
      } else {
        console.error(TEMPLATE_TAG, 'shape shadow offset json error:', JSON.stringify(jsonParam.shadowOffset));
      }
    }
  }

  _createCenterlineShape() {
    //create shape inline
    this.m_centerlineSolidStrokeDash = new Amaz$4.IFShapeStrokeDash();
    this.m_centerlineSolidStrokeDash.mode = Amaz$4.IFShapeStrokeDashMode.ADAPT;
    this.m_centerlineSolidStroke = new Amaz$4.IFShapeDrawSolidStroke();
    this.m_centerlineSolidStroke.sideType = bothSideType;
    this.m_centerlineSolidStroke.enable = false;
    this.m_centerlineSolidStroke.dash = this.m_centerlineSolidStrokeDash;
  }

  _createInlineShape() {
    //create shape inline
    this.m_inlineSolidStrokeDash = new Amaz$4.IFShapeStrokeDash();
    this.m_inlineSolidStrokeDash.mode = Amaz$4.IFShapeStrokeDashMode.ADAPT;
    this.m_inlineSolidStroke = new Amaz$4.IFShapeDrawSolidStroke();
    this.m_inlineSolidStroke.sideType = inlineSideType;
    this.m_inlineSolidStroke.enable = false;
    this.m_inlineSolidStroke.dash = this.m_inlineSolidStrokeDash;
  }

  _createOutlineShape() {
    this.m_outlineSolidStrokeDash = new Amaz$4.IFShapeStrokeDash();
    this.m_outlineSolidStrokeDash.mode = Amaz$4.IFShapeStrokeDashMode.ADAPT;
    this.m_outlineSolidStroke = new Amaz$4.IFShapeDrawSolidStroke();
    this.m_outlineSolidStroke.sideType = outlineSideType;
    this.m_outlineSolidStroke.enable = false;
    this.m_outlineSolidStroke.dash = this.m_outlineSolidStrokeDash;
  }

  _createShapeRoundCorner() {
    this.m_shapeRoundCorner = new Amaz$4.IFShapeRoundCorner();
  }

  _createCustomPointShapeGroup() {
    // create shape
    this.m_shapeContourPath = new Amaz$4.IFShapeContourPath();
    this.m_shapeSolidFill = new Amaz$4.IFShapeDrawSolidFill();

    this._createInlineShape();

    this._createCenterlineShape();

    this._createOutlineShape(); //create shape  shadow group


    this.m_shapeShadowContourPath = new Amaz$4.IFShapeContourPath();
    this.m_shapeShadowSolidFill = new Amaz$4.IFShapeDrawSolidFill();
    this.m_shadowGroup = new Amaz$4.IFShapeGroup();
    const shadowVector = new Amaz$4.Vector();
    shadowVector.pushBack(this.m_shapeShadowContourPath);
    shadowVector.pushBack(this.m_shapeShadowSolidFill);
    this.m_shadowGroup.shapeElements = shadowVector;
    this.m_shadowGroup.enable = false; // create round corner for custom point contour

    this._createShapeRoundCorner();

    return true;
  }

  _createEllipseShapeGroup() {
    //create ellipse
    this.m_shapeContourEllipse = new Amaz$4.IFShapeContourEllipse();
    this.m_shapeSolidFill = new Amaz$4.IFShapeDrawSolidFill();

    this._createInlineShape();

    this._createCenterlineShape();

    this._createOutlineShape(); //create shape shadow ellipse


    this.m_shapeShadowContourEllipse = new Amaz$4.IFShapeContourEllipse();
    this.m_shapeShadowSolidFill = new Amaz$4.IFShapeDrawSolidFill();
    this.m_shadowGroup = new Amaz$4.IFShapeGroup();
    const shadowVector = new Amaz$4.Vector();
    shadowVector.pushBack(this.m_shapeShadowContourEllipse);
    shadowVector.pushBack(this.m_shapeShadowSolidFill);
    this.m_shadowGroup.shapeElements = shadowVector;
    this.m_shadowGroup.enable = false;
  }

  _createLine() {
    this.m_shapeContourPath = new Amaz$4.IFShapeContourPath();
    this.m_shapeContourPath.closed = false;
    this.m_shapeLineStrokeDash = new Amaz$4.IFShapeStrokeDash();
    this.m_shapeLineStroke = new Amaz$4.IFShapeDrawSolidStroke();
    this.m_shapeLineStroke.sideType = bothSideType;
    this.m_shapeLineStroke.dash = this.m_shapeLineStrokeDash;
    this.m_shapeShadowContourPath = new Amaz$4.IFShapeContourPath();
    this.m_shapeShadowContourPath.closed = false;
    this.m_shapeShadowLineStrokeDash = new Amaz$4.IFShapeStrokeDash();
    this.m_shapeShadowLineStroke = new Amaz$4.IFShapeDrawSolidStroke();
    this.m_shapeShadowLineStroke.sideType = bothSideType;
    this.m_shapeShadowLineStroke.dash = this.m_shapeShadowLineStrokeDash;
    this.m_shadowGroup = new Amaz$4.IFShapeGroup();
    const shadowVector = new Amaz$4.Vector();
    shadowVector.pushBack(this.m_shapeShadowContourPath);
    shadowVector.pushBack(this.m_shapeShadowLineStroke);
    this.m_shadowGroup.shapeElements = shadowVector;
    this.m_shadowGroup.enable = false;
  }

  _createArrow() {
    // for arrow un and down line, points control don't need update by json
    const arrowPointsVec = new Amaz$4.Vec2Vector();
    this.m_shapeContourPath = new Amaz$4.IFShapeContourPath();
    this.m_shapeContourPath.closed = false;
    this.m_shapeCotourPathArrow = new Amaz$4.IFShapeContourPath();
    this.m_shapeCotourPathArrow.pathInDirs = arrowPointsVec;
    this.m_shapeCotourPathArrow.pathOutDirs = arrowPointsVec;
    this.m_shapeArrowSolidFill = new Amaz$4.IFShapeDrawSolidFill();
    this.m_shapeArrowGroup = new Amaz$4.IFShapeGroup();
    const shapeArrowArr = new Amaz$4.Vector();
    shapeArrowArr.pushBack(this.m_shapeCotourPathArrow);
    shapeArrowArr.pushBack(this.m_shapeArrowSolidFill);
    this.m_shapeArrowGroup.shapeElements = shapeArrowArr;
    this.m_shapeLineStrokeDash = new Amaz$4.IFShapeStrokeDash();
    this.m_shapeLineStroke = new Amaz$4.IFShapeDrawSolidStroke();
    this.m_shapeLineStroke.sideType = bothSideType;
    this.m_shapeLineStroke.dash = this.m_shapeLineStrokeDash;
    this.m_shapeShadowContourPath = new Amaz$4.IFShapeContourPath();
    this.m_shapeShadowContourPath.closed = false;
    this.m_shapeShadowCotourPathArrow = new Amaz$4.IFShapeContourPath();
    this.m_shapeShadowCotourPathArrow.pathInDirs = arrowPointsVec;
    this.m_shapeShadowCotourPathArrow.pathOutDirs = arrowPointsVec;
    this.m_shapeShadowArrowSolidFill = new Amaz$4.IFShapeDrawSolidFill();
    this.m_shapeShadowArrowGroup = new Amaz$4.IFShapeGroup();
    const shapeShadowArrowArr = new Amaz$4.Vector();
    shapeShadowArrowArr.pushBack(this.m_shapeShadowCotourPathArrow);
    shapeShadowArrowArr.pushBack(this.m_shapeShadowArrowSolidFill);
    this.m_shapeShadowArrowGroup.shapeElements = shapeShadowArrowArr;
    this.m_shapeShadowLineStrokeDash = new Amaz$4.IFShapeStrokeDash();
    this.m_shapeShadowLineStroke = new Amaz$4.IFShapeDrawSolidStroke();
    this.m_shapeShadowLineStroke.sideType = bothSideType;
    this.m_shapeShadowLineStroke.dash = this.m_shapeShadowLineStrokeDash;
    this.m_shadowGroup = new Amaz$4.IFShapeGroup();
    const shadowVector = new Amaz$4.Vector();
    shadowVector.pushBack(this.m_shapeShadowContourPath);
    shadowVector.pushBack(this.m_shapeShadowLineStroke);
    shadowVector.pushBack(this.m_shapeShadowArrowGroup);
    this.m_shadowGroup.shapeElements = shadowVector;
    this.m_shadowGroup.enable = false;
  }

  _packageShape(shapeType) {
    this.m_shapeGroup = new Amaz$4.IFShapeGroup();
    const shapeVector = new Amaz$4.Vector();

    if (shapeType === ShapeType.CUSTOM_CONTOUR_POLYGON || shapeType === ShapeType.LINE) {
      if (this.m_shapeContourPath) {
        shapeVector.pushBack(this.m_shapeContourPath);
      }

      if (this.m_shapeLineStroke && shapeType === ShapeType.LINE) {
        shapeVector.pushBack(this.m_shapeLineStroke);
      }
    } else if (shapeType === ShapeType.CONTOUR_ELLIPSE) {
      if (this.m_shapeContourEllipse) {
        shapeVector.pushBack(this.m_shapeContourEllipse);
      }
    } else if (shapeType === ShapeType.ARROW) {
      if (this.m_shapeContourPath && this.m_shapeArrowGroup && this.m_shapeLineStroke) {
        shapeVector.pushBack(this.m_shapeContourPath);
        shapeVector.pushBack(this.m_shapeLineStroke);
        shapeVector.pushBack(this.m_shapeArrowGroup);
      }
    }

    if (this.m_outlineSolidStroke) {
      shapeVector.pushBack(this.m_outlineSolidStroke);
    }

    if (this.m_centerlineSolidStroke) {
      shapeVector.pushBack(this.m_centerlineSolidStroke);
    }

    if (this.m_inlineSolidStroke) {
      shapeVector.pushBack(this.m_inlineSolidStroke);
    }

    if (this.m_shapeSolidFill) {
      shapeVector.pushBack(this.m_shapeSolidFill);
    }

    if (this.m_shadowGroup) {
      shapeVector.pushBack(this.m_shadowGroup);
    }

    if (this.m_shapeRoundCorner) {
      shapeVector.pushBack(this.m_shapeRoundCorner);
    }

    this.m_shapeGroup.shapeElements = shapeVector;
    this.m_shapeGroup.alpha = this.globalAlpha;

    if (this.m_shapeCom) {
      const shape = new Amaz$4.Vector();
      shape.pushBack(this.m_shapeGroup);
      this.m_shapeCom.shapeElements = shape;
    }
  }

  _createShapeGroup(jsonParameters) {
    if (null !== jsonParameters) {
      const jsonParam = jsonParameters;

      if ('shape_params' in jsonParam) {
        const configJson = jsonParam.shape_params;

        if (configJson) {
          if ('shape_type' in configJson) {
            const shapeType = configJson.shape_type;
            this.shapeType = shapeType;

            if (shapeType === ShapeType.CUSTOM_CONTOUR_POLYGON) {
              this._createCustomPointShapeGroup();
            } else if (shapeType === ShapeType.CONTOUR_ELLIPSE) {
              this._createEllipseShapeGroup();
            } else if (shapeType === ShapeType.LINE) {
              this._createLine();
            } else if (shapeType === ShapeType.ARROW) {
              this._createArrow();
            }

            this._packageShape(this.shapeType);
          } else {
            console.error(TEMPLATE_TAG, 'createShapeGroup failed, parameters not have shape_type!');
          }
        } else {
          console.error(TEMPLATE_TAG, 'createShapeGroup failed, parameters shape_params is null or undefined!');
        }
      } else {
        console.error(TEMPLATE_TAG, 'createShapeGroup failed, parameters not have shape_params!');
      }
    }
  }

  static createShapeBlendMat() {
    const semantics = new Amaz$4.Map();
    semantics.insert('position', Amaz$4.VertexAttribType.POSITION);
    semantics.insert('texcoord0', Amaz$4.VertexAttribType.TEXCOORD0);
    const rs = new Amaz$4.RenderState();
    rs.depthstencil = new Amaz$4.DepthStencilState();
    rs.depthstencil.depthTestEnable = false;
    rs.depthstencil.depthWriteEnable = false;
    rs.colorBlend = new Amaz$4.ColorBlendState();
    const colorAtt = new Amaz$4.ColorBlendAttachmentState();
    colorAtt.colorWriteMask = 15;
    colorAtt.blendEnable = true;
    colorAtt.srcColorBlendFactor = Amaz$4.BlendFactor.ONE;
    colorAtt.dstColorBlendFactor = Amaz$4.BlendFactor.ONE_MINUS_SRC_ALPHA;
    colorAtt.srcAlphaBlendFactor = Amaz$4.BlendFactor.ONE;
    colorAtt.dstAlphaBlendFactor = Amaz$4.BlendFactor.ONE_MINUS_SRC_ALPHA;
    const attVec = new Amaz$4.Vector();
    attVec.pushBack(colorAtt);
    rs.colorBlend.attachments = attVec;
    const vertex_shaders = `
    precision highp float;
    attribute vec3 position;
    attribute vec2 texcoord0;
    varying vec2 uv0;
    void main() 
    {
        gl_Position = vec4(position.xyz, 1.0);
        uv0 = texcoord0;
    }

  `;
    const fragment_shaders = `
    precision lowp float;
    varying vec2 uv0;
    uniform sampler2D _MainTex;
    uniform float u_alpha;
    void main()
    {
      vec4 u_color = texture2D(_MainTex, uv0);
      gl_FragColor = vec4(u_color.rgb * u_alpha, u_color.a * u_alpha);
    }
  `;
    const xs = new Amaz$4.XShader();
    const vs = new Amaz$4.Shader();
    vs.type = Amaz$4.ShaderType.VERTEX;
    vs.source = vertex_shaders;
    const fs = new Amaz$4.Shader();
    fs.type = Amaz$4.ShaderType.FRAGMENT;
    fs.source = fragment_shaders;
    const shaderVec = new Amaz$4.Vector();
    shaderVec.pushBack(vs);
    shaderVec.pushBack(fs);
    const platShaderMap = new Amaz$4.Map();
    platShaderMap.insert('gles2', shaderVec);
    const pass = new Amaz$4.Pass();
    pass.semantics = semantics;
    pass.shaders = platShaderMap;
    pass.renderState = rs;
    const passVec = new Amaz$4.Vector();
    passVec.pushBack(pass);
    xs.passes = passVec;
    const material = new Amaz$4.Material();
    material.xshader = xs;
    material.renderQueue = 1;
    return material;
  }

  _creatShapeBlendEntity(scene) {
    const renderEntityName = this.m_name + 'shapeBlendRenderEntity';
    this.m_shapeBlendEntity = AmazUtils$1.createEntity(renderEntityName, scene);
    this.m_shapeBlendEntity.layer = this.m_cameraLayer;
    const localPos = new Vec3$2(0.0, 0.0, 0.0);
    const scale = new Vec3$2(1.0, 1.0, 1.0);
    const rotate = new Vec3$2(0.0, 0.0, 0.0); // add transform component to render entity

    this.m_shapeBlendEntity.transform = {
      position: localPos,
      scale: scale,
      rotation: rotate
    };
    this.m_shapeBlendMeshRenderer = this.m_shapeBlendEntity.addComponent('MeshRenderer');
    const quadMesh = AmazUtils$1.CreateQuadMesh();
    this.m_shapeBlendMeshRenderer.mesh = quadMesh;
    const material = Shape.createShapeBlendMat();
    this.m_shapeBlendMeshRenderer.sharedMaterial = material;
    this.m_shapeBlendMeshRenderer.sortingOrder = this.m_layer * LAYER_SIZE + this.m_localOrder * ORDER_SIZE + 1;

    if (null != this.m_rootEntity) {
      AmazUtils$1.addChildEntity(this.m_rootEntity, this.m_shapeBlendEntity);
    }
  }

  _createShapeEntity(scene) {
    const renderEntityName = this.m_name + 'renderEntity';
    this.m_renderEntity = AmazUtils$1.createEntity(renderEntityName, scene);
    this.m_renderEntity.layer = this.m_cameraLayer;
    const localPos = new Vec3$2(0.0, 0.0, 0.0);
    const scale = new Vec3$2(1.0, 1.0, 1.0);
    const rotate = new Vec3$2(0.0, 0.0, 0.0); // add transform component to render entity

    this.m_renderEntity.transform = {
      position: localPos,
      scale: scale,
      rotation: rotate
    };
    this.m_renderEntity.addComponent('IFShape');
    this.m_renderEntity.addComponent('MeshRenderer');
    this.m_shapeCom = this.m_renderEntity.getComponent('IFShape');
    this.m_renderRTTexture = new Amaz$4.RenderTexture();
    this.m_renderRTTexture.massMode = Amaz$4.MSAAMode._4X;
    this.m_shapeCom.setRenderTexture(this.m_renderRTTexture);
    this.createWidgetRootEntity(scene);

    if (null != this.m_rootEntity) {
      AmazUtils$1.addChildEntity(this.m_rootEntity, this.m_renderEntity);
    }
  }

  updateShapeParameters(jsonParam, shapeType) {
    if ('shape_params' in jsonParam) {
      const configJson = jsonParam.shape_params;

      this._updateShapeBaseParameters(configJson);

      if (this.m_originalPixelSizeDirty) {
        this.updateShapeWH();
        this.m_originalPixelSizeDirty = false;
      }

      if (shapeType === ShapeType.CUSTOM_CONTOUR_POLYGON || shapeType === ShapeType.LINE || shapeType === ShapeType.ARROW) {
        this._updateShapeCustomPoints(configJson);
      }

      if (shapeType === ShapeType.CUSTOM_CONTOUR_POLYGON || shapeType === ShapeType.CONTOUR_ELLIPSE) {
        this._updateShapeInline(configJson);

        this._updateShapeCenterline(configJson);

        this._updateShapeOutline(configJson);
      }

      this._updateShapeShadow(configJson);
    }
  }

  updateShape() {
    if (this.m_needUpdateShape && this.m_shapeCom) {
      if (this.m_shapeParameters) {
        this.updateShapeParameters(this.m_shapeParameters, this.shapeType);
      } else {
        console.error(TEMPLATE_TAG, 'shape json parameters is null or undefined!');
      }

      this.m_needUpdateShape = false;
    }
  }

  onUpdate(timeStamp) {
    if (!this.m_enable || !this.checkIsInRange(timeStamp)) {
      //if out of time range and then UI check visible, so need first update and then set visible false.
      super.onUpdate(timeStamp);

      if (this.m_rootEntity && this.m_rootEntity.visible) {
        this.m_rootEntity.visible = false;
        this.resetAllAnimation();
      }

      if (this.m_shapeBlendEntity && this.m_shapeBlendEntity.visible) {
        this.m_shapeBlendEntity.visible = false;
      }

      return;
    } else {
      if (this.m_rootEntity && !this.m_rootEntity.visible) {
        this.m_rootEntity.visible = true;
      }

      if (this.m_shapeBlendEntity && !this.m_shapeBlendEntity.visible) {
        this.m_shapeBlendEntity.visible = true;
      }

      super.onUpdate(timeStamp);

      if (this.m_screenSizeChanged) {
        if (this.m_renderRTTexture) {
          this.m_renderRTTexture.width = this.m_screenSize.x;
          this.m_renderRTTexture.height = this.m_screenSize.y;
        }

        this.m_screenSizeChanged = false;
      } // animation script may change shape global alpha.


      this.seekAnimations(timeStamp);
      let shapeGlobalAlpha = 1.0;

      if (this.m_shapeCom) {
        shapeGlobalAlpha = this.m_shapeCom.shapeGlobalAlpha;
      }

      if (this.m_renderRTTexture && this.m_shapeBlendMeshRenderer) {
        const material = this.m_shapeBlendMeshRenderer.sharedMaterial;

        if (material) {
          material.setTex('_MainTex', this.m_renderRTTexture);
          material.setFloat('u_alpha', this.globalAlpha * shapeGlobalAlpha);
        }
      }
    }
  }

}

var Amaz$3 = effect.Amaz;
var Vec3$1 = Amaz$3.Vector3f;

const pipe = (...fns) => x => fns.reduce((v, f) => f(v), x);

function syncLoadPrefabEntity(path, scene) {
  const utils = new Amaz$3.SwingTemplateUtils();
  const prefab = utils.parseInfoSticker(path, 0, false, 0); // const prefab = Amaz.parseInfoSticker(path);

  if (!prefab) return undefined;
  const nativeEntity = scene.addInstantiatedPrefab(prefab); // texture size for anim, copy texturesize to instantiated sprite
  // is this necessary?

  const renderer = nativeEntity.getComponent('Sprite2DRenderer');
  renderer.setTextureSize(prefab.getRootEntity().getComponent('Sprite2DRenderer').getTextureSize());
  AmazUtils$1.initAmazEntity(nativeEntity);
  return nativeEntity;
}

class SpriteUtils {
  static recursiveSetLayer(entity, layer_id) {
    if (entity == null) return;
    entity.layer = layer_id;
    const trans = entity.getComponent('Transform');

    for (let i = 0; i = trans.children.size(); ++i) {
      SpriteUtils.recursiveSetLayer(trans.children.get(i).entity, layer_id);
    }
  }

  static loadSeqAnimSticker(sprite, path) {
    const animSeqs = [];
    if (!sprite.scene) return animSeqs;
    const rootEntity = sprite.rootEntity;
    const nativeScene = sprite.scene;
    const rootDir = nativeScene.assetMgr.rootDir; // maybe relative path or absolute path

    let tryPath = path;
    const utils = new Amaz$3.SwingTemplateUtils();

    if (!utils.isFileExist(path) && !utils.isDir(path)) {
      tryPath = rootDir + path;
    }

    const prefabEntity = syncLoadPrefabEntity(tryPath, nativeScene);
    if (prefabEntity == undefined || rootEntity == null) return [];
    prefabEntity.name = 'prefab_entity';
    SpriteUtils.recursiveSetLayer(prefabEntity, sprite.cameraLayer);
    AmazUtils$1.addChildEntity(rootEntity, prefabEntity);
    sprite.renderEntity = prefabEntity;
    const AnimSeqTypes = ['AnimSeqComponent', 'GifAnimSeq', 'VideoAnimSeq'];
    AnimSeqTypes.forEach(type => {
      const comp = prefabEntity === null || prefabEntity === void 0 ? void 0 : prefabEntity.getComponent(type);

      if (comp) {
        animSeqs.push(comp);
      }
    });
    return animSeqs;
  }

  static setSpriteDataProperties(inputState, targetState, propName, dirtyCallback = undefined) {
    if (inputState.data != null && inputState.data[propName] != null && targetState[propName] != inputState.data[propName]) {
      targetState[propName] = inputState.data[propName];

      if (dirtyCallback != null) {
        return dirtyCallback(inputState.data[propName]);
      }
    }

    return true;
  }

}

class Sprite extends Widget2D {
  constructor(name, widgetType, scene, params) {
    super(name, widgetType, scene); // props is current state. params is pending params to be updated.

    this.props = {
      timestamp: 0,
      data: {
        name: '',
        type: 'sticker'
      },
      layer: 0
    }; // params: {
    //   configData?: SpriteData;
    //   layoutData?: ConstraintAttributs;
    //   timestamp?: number;
    // } = {};

    this.animseqs = [];
    this.pendingStateClosure = [];
    this.pipeline = undefined;
    this.parameters = params;
    this.pipeline = this.generatePipline();
    this.collectStates();
  }

  makeStateClosure(param) {
    return () => {
      this.updateStates(param);
    };
  }

  set state(param) {
    if (param) this.pendingStateClosure.push(this.makeStateClosure(param));
  }

  get state() {
    return this.props;
  }

  set parameters(params) {
    var _a;

    if (params instanceof String) {
      params = JSON.parse(params);
    }

    let timestamp;

    if ('timestamp' in params) {
      timestamp = params.timestamp;
    }

    const configData = TemplateConfigParser.parseSpriteConfig(params);
    this.state = {
      data: configData,
      timestamp: timestamp
    };
    (_a = configData === null || configData === void 0 ? void 0 : configData.anims) === null || _a === void 0 ? void 0 : _a.forEach(animData => {
      const anim = TemplateConfigParser.parseAnimationConfig(animData);

      if (anim) {
        const anim_script_type = anim.anim_script_type;

        if (anim) {
          super.setWidgetAnimation(anim.anim_resource_path, anim.anim_resource_id, anim_script_type, anim.anim_start_time, anim.duration, anim.loop_duration, AnimationType[anim.anim_type]);
        }
      }
    });
  }

  get parameters() {
    const widget2DParam = super.getParameters();
    const data = this.props.data;
    data.original_size = widget2DParam.original_size;
    data.anims = widget2DParam.anims;
    return data;
  }

  onInit() {}

  onUpdate(_timestamp) {
    this.state = {
      timestamp: _timestamp
    };
    this.collectStates();
  }

  onDestroy() {}

  onRender() {}

  collectStates() {
    const pendings = this.pendingStateClosure;
    this.pendingStateClosure = [];
    pendings.forEach(closure => closure());
  }

  generatePipline() {
    // set param to properties
    const setSpriteDataProperties = SpriteUtils.setSpriteDataProperties;

    const setGuid = inputState => (setSpriteDataProperties(inputState, this.props.data, 'name'), inputState);

    const setLayer = inputState => (setSpriteDataProperties(inputState, this.props.data, 'layer', layer => this.layer = layer), inputState);

    const setOrder = inputState => (setSpriteDataProperties(inputState, this.props.data, 'order_in_layer', order => this.localOrder = order), inputState);

    const setVisible = inputState => (setSpriteDataProperties(inputState, this.props.data, 'visible', enable => this.enable = enable), inputState);

    const setTimeLogic = inputState => {
      setSpriteDataProperties(inputState, this.props.data, 'start_time', val => this.startTime = val);
      setSpriteDataProperties(inputState, this.props.data, 'duration', val => this.duration = val); // timestamp is not in SpriteData

      if (inputState.timestamp != null && inputState.timestamp != this.props.timestamp) {
        this.props.timestamp = inputState.timestamp;
      }

      if (!this.checkIsInRange(this.props.timestamp) || !this.enable) {
        //if out of time range and then UI check visible, so need first update and then set visible false.
        super.onUpdate(this.props.timestamp);

        if (this.m_rootEntity && this.m_rootEntity.visible) {
          this.m_rootEntity.visible = false;
          this.resetAllAnimation();
        }
      } else {
        if (this.m_rootEntity && !this.m_rootEntity.visible) {
          this.m_rootEntity.visible = true;
        }

        super.onUpdate(this.props.timestamp);
        const seekTime = this.props.timestamp - this.startTime;
        this.animseqs.forEach(seq => seq.seekToTime(seekTime));
        this.seekAnimations(this.props.timestamp);
      }

      return inputState;
    };

    const setTransform = inputState => {
      setSpriteDataProperties(inputState, this.props.data, 'position', pos => {
        this.props.data.position = pos;
        this.position = new Vec3$1(pos[0], pos[1], pos[2]);
        return true;
      });
      setSpriteDataProperties(inputState, this.props.data, 'rotation', rot => {
        this.props.data.rotation = rot;
        this.rotation = new Vec3$1(rot[0], rot[1], rot[2]);
        return true;
      });
      setSpriteDataProperties(inputState, this.props.data, 'scale', sca => {
        this.props.data.scale = sca;
        this.scale = new Vec3$1(sca[0], sca[1], sca[2]);
        return true;
      });
      return inputState;
    }; // update sticker states


    const setSticker = inputState => {
      setSpriteDataProperties(inputState, this.props.data, 'sticker_design_type', design_type => {
        //design_type is 0, it means the sticker came from the background database
        //design_type is 1, it means the sticker came from the local material
        if (design_type === 0 || design_type === 1) {
          setSpriteDataProperties(inputState, this.props.data, 'sticker_path', path => {
            this.animseqs = SpriteUtils.loadSeqAnimSticker(this, path);
            return true;
          });
          return true;
        } else {
          // TODO
          console.error(TEMPLATE_TAG, 'not implemented yet:  ', design_type);
        }

        return false;
      });
      setSpriteDataProperties(inputState, this.props.data, 'sticker_loop', loop => {
        var _a;

        (_a = this.animseqs) === null || _a === void 0 ? void 0 : _a.forEach(anim => anim.playmode = loop ? Amaz$3.PlayMode.loop : Amaz$3.PlayMode.once);
        return true;
      });
      return inputState;
    };

    const setStickerRenderState = inputState => {
      // set sticker_alpha
      setSpriteDataProperties(inputState, this.props.data, 'sticker_alpha', alpha => {
        var _a;

        const renderers = (_a = this.renderEntity) === null || _a === void 0 ? void 0 : _a.getComponentsRecursive('Renderer');

        if (renderers != null) {
          for (let i = 0; i < (renderers === null || renderers === void 0 ? void 0 : renderers.size()); ++i) {
            const renderer = renderers.get(i);

            if (renderer instanceof Amaz$3.Sprite2DRenderer) {
              renderer.color = new Amaz$3.Vector4f(alpha, alpha, alpha, alpha);
            }
          }
        }

        return true;
      }); // set sticker_flipX

      setSpriteDataProperties(inputState, this.props.data, 'sticker_flipX', mirror => {
        var _a;

        const renderer = (_a = this.renderEntity) === null || _a === void 0 ? void 0 : _a.getComponent('Renderer');

        if (renderer != null && renderer instanceof Amaz$3.Sprite2DRenderer) {
          renderer.mirror = mirror;
        }

        return true;
      }); // flipY

      setSpriteDataProperties(inputState, this.props.data, 'sticker_flipY', flip => {
        var _a;

        const renderer = (_a = this.renderEntity) === null || _a === void 0 ? void 0 : _a.getComponent('Renderer');

        if (renderer != null && renderer instanceof Amaz$3.Sprite2DRenderer) {
          renderer.flip = flip;
        }

        return true;
      });
      return inputState;
    };

    return pipe(setGuid, setSticker, setStickerRenderState, setLayer, setOrder, setTransform, setVisible, setTimeLogic);
  }

  updateStates(stateData) {
    var _a;

    (_a = this.pipeline) === null || _a === void 0 ? void 0 : _a.call(this, stateData);
  }

}

var Amaz$2 = effect.Amaz;
var Rect = Amaz$2.Rect;
var Vec3 = Amaz$2.Vector3f;
var Vec2 = Amaz$2.Vector2f; // TODO: if update effect sdk version, need check this emum, 1180 is different
// from this

var TextCommandType;

(function (TextCommandType) {
  TextCommandType[TextCommandType["CT_ENTER_EDIT_STATE"] = 0] = "CT_ENTER_EDIT_STATE";
  TextCommandType[TextCommandType["CT_EXIT_EDIT_STATE"] = 1] = "CT_EXIT_EDIT_STATE";
  TextCommandType[TextCommandType["CT_INPUT_STR"] = 2] = "CT_INPUT_STR";
  TextCommandType[TextCommandType["CT_INPUT_RICH_STR"] = 3] = "CT_INPUT_RICH_STR";
  TextCommandType[TextCommandType["CT_BACK_DELETE"] = 4] = "CT_BACK_DELETE";
  TextCommandType[TextCommandType["CT_FORWARD_DELETE"] = 5] = "CT_FORWARD_DELETE";
  TextCommandType[TextCommandType["CT_START_COMPOSE"] = 6] = "CT_START_COMPOSE";
  TextCommandType[TextCommandType["CT_PREEDIT_COMPOSE"] = 7] = "CT_PREEDIT_COMPOSE";
  TextCommandType[TextCommandType["CT_END_COMPOSE"] = 8] = "CT_END_COMPOSE";
  TextCommandType[TextCommandType["CT_FORCE_REFRESH"] = 9] = "CT_FORCE_REFRESH";
  TextCommandType[TextCommandType["CT_MOVE_CURSOR_LR"] = 16] = "CT_MOVE_CURSOR_LR";
  TextCommandType[TextCommandType["CT_MOVE_CURSOR_UPDOWN"] = 17] = "CT_MOVE_CURSOR_UPDOWN";
  TextCommandType[TextCommandType["CT_MOVE_CURSOR_LINE_BEGIN_END"] = 18] = "CT_MOVE_CURSOR_LINE_BEGIN_END";
  TextCommandType[TextCommandType["CT_MOVE_CURSOR_BY_INDEX"] = 19] = "CT_MOVE_CURSOR_BY_INDEX";
  TextCommandType[TextCommandType["CT_MOVE_CURSOR_BY_POS"] = 20] = "CT_MOVE_CURSOR_BY_POS";
  TextCommandType[TextCommandType["CT_MOVE_SELECT_HANDLE_BY_POS"] = 21] = "CT_MOVE_SELECT_HANDLE_BY_POS";
  TextCommandType[TextCommandType["CT_SELECT_CONTENT"] = 32] = "CT_SELECT_CONTENT";
  TextCommandType[TextCommandType["CT_SELECT_LR_CONTENT"] = 33] = "CT_SELECT_LR_CONTENT";
  TextCommandType[TextCommandType["CT_SELECT_UPDOWN_CONTENT"] = 34] = "CT_SELECT_UPDOWN_CONTENT";
  TextCommandType[TextCommandType["CT_SELECT_MOUSE_CONTENT"] = 35] = "CT_SELECT_MOUSE_CONTENT";
  TextCommandType[TextCommandType["CT_SELECT_ALL_CONTENT"] = 36] = "CT_SELECT_ALL_CONTENT";
  TextCommandType[TextCommandType["CT_EDIT_FONT"] = 48] = "CT_EDIT_FONT";
  TextCommandType[TextCommandType["CT_EDIT_COLOR"] = 49] = "CT_EDIT_COLOR";
  TextCommandType[TextCommandType["CT_EDIT_ALPHA"] = 50] = "CT_EDIT_ALPHA";
  TextCommandType[TextCommandType["CT_EDIT_BGCOLOR"] = 51] = "CT_EDIT_BGCOLOR";
  TextCommandType[TextCommandType["CT_EDIT_BG_ALPHA"] = 52] = "CT_EDIT_BG_ALPHA";
  TextCommandType[TextCommandType["CT_EDIT_SIZE"] = 53] = "CT_EDIT_SIZE";
  TextCommandType[TextCommandType["CT_EDIT_BOLD"] = 54] = "CT_EDIT_BOLD";
  TextCommandType[TextCommandType["CT_EDIT_ITALIC"] = 55] = "CT_EDIT_ITALIC";
  TextCommandType[TextCommandType["CT_EDIT_UNDERLINE"] = 56] = "CT_EDIT_UNDERLINE";
  TextCommandType[TextCommandType["CT_EDIT_OUTLINE"] = 57] = "CT_EDIT_OUTLINE";
  TextCommandType[TextCommandType["CT_EDIT_OUTLINE_COLOR"] = 58] = "CT_EDIT_OUTLINE_COLOR";
  TextCommandType[TextCommandType["CT_EDIT_OUTLINE_ALPHA"] = 59] = "CT_EDIT_OUTLINE_ALPHA";
  TextCommandType[TextCommandType["CT_EDIT_OUTLINE_WIDTH"] = 60] = "CT_EDIT_OUTLINE_WIDTH";
  TextCommandType[TextCommandType["CT_EDIT_SHADOW"] = 61] = "CT_EDIT_SHADOW";
  TextCommandType[TextCommandType["CT_EDIT_SHADOW_COLOR"] = 62] = "CT_EDIT_SHADOW_COLOR";
  TextCommandType[TextCommandType["CT_EDIT_SHADOW_ALPHA"] = 63] = "CT_EDIT_SHADOW_ALPHA";
  TextCommandType[TextCommandType["CT_EDIT_SHADOW_SMOOTH"] = 64] = "CT_EDIT_SHADOW_SMOOTH";
  TextCommandType[TextCommandType["CT_EDIT_SHADOW_OFFSET"] = 65] = "CT_EDIT_SHADOW_OFFSET";
  TextCommandType[TextCommandType["CT_EDIT_EFFECT_STYLE"] = 66] = "CT_EDIT_EFFECT_STYLE";
  TextCommandType[TextCommandType["CT_EDIT_TEXT_PRESET_STYLE_PARAM"] = 67] = "CT_EDIT_TEXT_PRESET_STYLE_PARAM";
  TextCommandType[TextCommandType["CT_EDIT_TEXT_PARAM"] = 68] = "CT_EDIT_TEXT_PARAM";
  TextCommandType[TextCommandType["CT_EDIT_TEMPLATE_TEXT_STYLE"] = 69] = "CT_EDIT_TEMPLATE_TEXT_STYLE";
  TextCommandType[TextCommandType["CT_EDIT_RESET_TEXT_CONTEXT"] = 70] = "CT_EDIT_RESET_TEXT_CONTEXT";
  TextCommandType[TextCommandType["CT_EDIT_DEFAULT_STYLE"] = 71] = "CT_EDIT_DEFAULT_STYLE";
  TextCommandType[TextCommandType["CT_EDIT_CONVERT_CASE"] = 72] = "CT_EDIT_CONVERT_CASE";
  TextCommandType[TextCommandType["CT_EDIT_FILL"] = 73] = "CT_EDIT_FILL";
  TextCommandType[TextCommandType["CT_EDIT_MULTI_STROKE"] = 74] = "CT_EDIT_MULTI_STROKE";
  TextCommandType[TextCommandType["CT_EDIT_MULTI_SHADOW"] = 75] = "CT_EDIT_MULTI_SHADOW";
  TextCommandType[TextCommandType["CT_EDIT_MULTI_SHADOW_STROKE"] = 76] = "CT_EDIT_MULTI_SHADOW_STROKE";
  TextCommandType[TextCommandType["CT_EDIT_MULTI_INNER_SHADOW"] = 77] = "CT_EDIT_MULTI_INNER_SHADOW";
  TextCommandType[TextCommandType["CT_GET_PLAIN_STR"] = 256] = "CT_GET_PLAIN_STR";
  TextCommandType[TextCommandType["CT_GET_RICH_STR"] = 257] = "CT_GET_RICH_STR";
  TextCommandType[TextCommandType["CT_GET_CURSOR_RECT"] = 258] = "CT_GET_CURSOR_RECT";
  TextCommandType[TextCommandType["CT_GET_CURSOR_CHAR_INDEX"] = 259] = "CT_GET_CURSOR_CHAR_INDEX";
  TextCommandType[TextCommandType["CT_GET_CHAR_RECT"] = 260] = "CT_GET_CHAR_RECT";
  TextCommandType[TextCommandType["CT_GET_SELECT_RANGE"] = 261] = "CT_GET_SELECT_RANGE";
  TextCommandType[TextCommandType["CT_GET_ERROR_INFO"] = 262] = "CT_GET_ERROR_INFO";
  TextCommandType[TextCommandType["CT_GET_EDIT_CONTEXT_INFO"] = 263] = "CT_GET_EDIT_CONTEXT_INFO";
  TextCommandType[TextCommandType["CT_GET_SELECT_HANDLE_RECT"] = 264] = "CT_GET_SELECT_HANDLE_RECT";
  TextCommandType[TextCommandType["CT_NONE"] = 512] = "CT_NONE";
})(TextCommandType || (TextCommandType = {}));
/**
 * @class
 * @category widget2d
 * @name RichText
 * @classdesc A RichText class provides capabilities for  create a rich text
 * entity and set/get text parameters, which inherited from widget2d.
 * @description Constructor to create a RichText instance.
 * @author ninghualong
 * @sdk 12.2.0
 */


class RichText extends Widget2D {
  constructor(name, widgetType, scene) {
    super(name, widgetType, scene);
    this.m_jsonPares = null;
    this.m_textComp = null;
    this.m_needUpdateTextCom = true;
    this.m_lineMaxWidth = -1;
    this.m_textInfoLayerWidth = -1;
    this.m_ktvColor = new Amaz$2.Vector4f();
    this.m_ktvOutlineColor = new Amaz$2.Vector4f();
    this.m_ktvShadowColor = new Amaz$2.Vector4f();
  }

  createRichText(jsonParam, scene) {
    this._createTextEntity(scene);

    this.parameters = jsonParam;
  }

  get textComp() {
    return this.m_textComp;
  }

  set parameters(jsonStr) {
    if (this.m_jsonPares != jsonStr && jsonStr) {
      this.m_jsonPares = jsonStr;
      this.m_needUpdateTextCom = true;
      super.setParameters(this.m_jsonPares);
      this.updateRootEntityParam();
      this.updateText();
    }
  }

  get parameters() {
    if (this.textComp) {
      const textCanvasColor = this.textComp.canvas.canvasColor;
      const textParam = {
        version: '2',
        richText: this.textComp.richStr,
        typeSettingKind: this.textComp.typeSettingParam.typeSettingKind,
        typeSettingAlign: this.textComp.typeSettingParam.typeSettingAlign,
        canvas: this.textComp.canvas.canvasEnabled,
        canvasColor: [textCanvasColor.x, textCanvasColor.y, textCanvasColor.z, textCanvasColor.w],
        canvasRoundCorner: this.textComp.canvas.canvasRoundCornerEnabled,
        canvasRoundRadius: this.textComp.canvas.canvasRoundRadius,
        canvasRoundRadiusScale: this.textComp.canvas.canvasRoundRadiusScale,
        canvasWrapped: this.textComp.canvas.canvasWrappText,
        canvasSplitThreshold: this.textComp.canvas.canvasSplitThreshold,
        canvasSplitPadding: this.textComp.canvas.canvasSplitPadding,
        canvasCustomized: this.textComp.canvas.canvasCustomizedEnabled,
        canvasWHCustomized: [this.textComp.canvas.canvasWHCustomized.x, this.textComp.canvas.canvasWHCustomized.y],
        canvasOffsetCustomized: [this.textComp.canvas.canvasOffsetCustomized.x, this.textComp.canvas.canvasOffsetCustomized.y],
        boldValue: this.textComp.activeTextStyle.boldValue,
        italicDegree: this.textComp.activeTextStyle.italicAngle,
        decorationWidth: this.textComp.activeTextStyle.decorationWidth,
        decorationOffset: this.textComp.activeTextStyle.decorationOffset,
        lineSpacing: this.textComp.typeSettingParam.lineSpacing,
        letterSpacing: this.textComp.typeSettingParam.letterSpacing,
        //right now innerpadding vertical and horizontal is the same.
        innerPadding: this.textComp.typeSettingParam.verticalPadding,
        lineMaxWidth: this.m_lineMaxWidth,
        fallbackFontPathList: [],
        oneLineCutOff: this.textComp.typeSettingParam.lineBreakType === Amaz$2.LineBreakType.CUT_OFF,
        cutOffPostfix: this.textComp.cutOffPostfix,
        shapePath: ' ',
        shapeFlipX: false,
        shapeFlipY: false,
        ktvColor: [this.m_ktvColor.x, this.m_ktvColor.y, this.m_ktvColor.z, this.m_ktvColor.w],
        ktvOutlineColor: [this.m_ktvOutlineColor.x, this.m_ktvOutlineColor.y, this.m_ktvOutlineColor.z, this.m_ktvOutlineColor.w],
        ktvShadowColor: [this.m_ktvShadowColor.x, this.m_ktvShadowColor.y, this.m_ktvShadowColor.z, this.m_ktvShadowColor.w],
        autoAdaptDpiEnabled: this.textComp.typeSettingParam.autoAdaptDpiEnabled,
        globalAlpha: this.textComp.globalAlpha,
        selectedColor: [this.textComp.selectColor.x, this.textComp.selectColor.y, this.textComp.selectColor.z, this.textComp.selectColor.w],
        rootPath: this.textComp.rootPath,
        sdfTextAlpha: this.textComp.sdfTextAlpha
      };
      const fallbackFontPaths = this.textComp.fallbackFontPaths;

      for (let i = 0; i < fallbackFontPaths.size(); i++) {
        const fontPath = fallbackFontPaths.get(i);
        textParam.fallbackFontPathList.push(fontPath);
      }

      const widgetParam = super.parameters;
      const widget2DParam = super.getParameters();
      const richTextParamData = {
        name: widgetParam.name,
        type: widgetParam.type,
        position: widgetParam.position,
        rotation: widgetParam.rotation,
        scale: widgetParam.scale,
        order_in_layer: widgetParam.order_in_layer,
        start_time: widgetParam.start_time,
        duration: widgetParam.duration,
        layout_params: widget2DParam.layout_params,
        original_size: widget2DParam.original_size,
        text_params: textParam,
        anims: widget2DParam.anims
      };
      return richTextParamData;
    } else {
      return '{}';
    }
  }

  set needUpdateTextCom(needed) {
    this.m_needUpdateTextCom = needed;
  }

  get needUpdateTextCom() {
    return this.m_needUpdateTextCom;
  }

  _convertPosBetweenRect(srcPos, srcRect, dstRect) {
    const srcRectCenter = new Vec2(srcRect.x + 0.5 * srcRect.width, srcRect.y + 0.5 * srcRect.height);
    const dstRectCenter = new Vec2(dstRect.x + 0.5 * dstRect.width, dstRect.y + 0.5 * dstRect.height);
    const real_pos = new Vec2(srcRectCenter.x + srcPos.x * srcRect.width * 0.5, srcRectCenter.y + srcPos.y * srcRect.height * 0.5);

    if (dstRect.width !== 0 && dstRect.height !== 0) {
      const dstPos = new Vec2((real_pos.x - dstRectCenter.x) / (dstRect.width * 0.5), (real_pos.y - dstRectCenter.y) / (dstRect.height * 0.5));
      return dstPos;
    } else {
      console.error(TEMPLATE_TAG, '_convertPosBetweenRect dstRect error.');
      const dstPos = new Vec2(srcPos.x, srcPos.y);
      return dstPos;
    }
  }

  setRichTextByOPCode(textOP, isSync) {
    let richTextStyleStr = textOP.m_sParam;

    if (null == this.m_textComp) {
      console.error(TEMPLATE_TAG, 'setRichTextByOPCode: text componet is null!');
      return;
    }

    if (textOP.m_iOpCode === TextCommandType.CT_EDIT_TEXT_PARAM) {
      const configJson = JSON.parse(richTextStyleStr);

      if (!configJson) {
        console.error(TEMPLATE_TAG, 'setRichTextByOPCode: CT_EDIT_TEXT_PARAM cmd read json failed!');
        return;
      } else {
        if ('richText' in configJson) {
          richTextStyleStr = configJson.richText;

          if (0 === richTextStyleStr.length) {
            if (!this.m_textComp.letters.empty()) {
              const firstLetter = this.m_textComp.letters.get(0);

              if (firstLetter instanceof Amaz$2.Letter) {
                this.m_textComp.recordReuseStyle(firstLetter);
              }
            }
          } else {
            this.m_textComp.recordReuseStyle(null);
          } // for some animation reload animation will call clear function,
          // which will reset text string by it's onStart record string.


          this.reloadAllAnimation();
          this.m_textComp.richStr = richTextStyleStr;
        }
      }

      this._updateTextParams(configJson);

      return;
    }

    if (textOP.m_iOpCode === TextCommandType.CT_EDIT_TEXT_PRESET_STYLE_PARAM) {
      const configJson = JSON.parse(richTextStyleStr);

      if (!configJson) {
        console.error(TEMPLATE_TAG, 'setRichTextByOPCode: CT_EDIT_TEXT_PARAM cmd read json failed!');
        return;
      } else {
        if ('richText' in configJson) {
          richTextStyleStr = configJson.richText;
        }
      }

      this._updateTextParams(configJson);
    }

    const textCmd = new Amaz$2.TextCommand();
    textCmd.type = textOP.m_iOpCode;

    if (TextCommandType.CT_MOVE_CURSOR_BY_POS === textCmd.type || TextCommandType.CT_SELECT_MOUSE_CONTENT === textCmd.type) {
      const x = -0.5 * this.m_widgetOriginalPixelSize.x;
      const y = -0.5 * this.m_widgetOriginalPixelSize.y;
      const text_rect = new Amaz$2.Rect(x, y, this.m_widgetOriginalPixelSize.x, this.m_widgetOriginalPixelSize.y);
      const canvas_rect = this.m_textComp.getCanvasCustomizedExpanded();
      const srcPos = new Vec2(textOP.m_fParam1, textOP.m_fParam2);

      const dstPos = this._convertPosBetweenRect(srcPos, text_rect, canvas_rect);

      textOP.m_fParam1 = dstPos.x;
      textOP.m_fParam2 = dstPos.y;
    }

    textCmd.iParam1 = textOP.m_fParam1;
    textCmd.iParam2 = textOP.m_fParam2;
    textCmd.iParam3 = textOP.m_fParam3;
    textCmd.iParam4 = textOP.m_fParam4;
    textCmd.sParam1 = richTextStyleStr;
    this.m_textComp.pushCommand(textCmd);
    const stringChanged = textCmd.type === TextCommandType.CT_INPUT_STR || textCmd.type === TextCommandType.CT_INPUT_RICH_STR || textCmd.type === TextCommandType.CT_BACK_DELETE || textCmd.type === TextCommandType.CT_FORWARD_DELETE || textCmd.type === TextCommandType.CT_PREEDIT_COMPOSE || textCmd.type === TextCommandType.CT_END_COMPOSE || textCmd.type === TextCommandType.CT_EDIT_RESET_TEXT_CONTEXT;
    const needUpdateRect = !this.m_textComp.typeSettingParam.textAdaptiveCanvasEnabled && (stringChanged || textCmd.type == TextCommandType.CT_FORCE_REFRESH || textCmd.type >= TextCommandType.CT_EDIT_FONT && textCmd.type <= TextCommandType.CT_EDIT_DEFAULT_STYLE);

    if (isSync || needUpdateRect) {
      if (stringChanged) {
        this.reloadAllAnimation();
      }

      this.m_textComp.forceFlushCommandQueue();
    }

    if (needUpdateRect) {
      const letterPosChanged = this.m_textComp.typeSettingDirty;
      this.m_textComp.forceTypeSetting();
      const rect = this.m_textComp.getCanvasCustomizedExpanded();
      const pixelSize = new Vec2(rect.width, rect.height);
      this.updateOriginaSize(pixelSize, this.m_screenSize);

      if (letterPosChanged) {
        this.reloadAllAnimation();
      }
    }
  }

  getRichTextByOPCode(textOP) {
    const resultTextOp = {
      m_iOpCode: TextCommandType.CT_NONE,
      m_fParam1: 0,
      m_fParam2: 0,
      m_fParam3: 0,
      m_fParam4: 0,
      m_sParam: ''
    };

    if (null == this.m_textComp) {
      console.error(TEMPLATE_TAG, 'getRichTextByOPCode: text componet is null!');
      return resultTextOp;
    }

    if (textOP.m_iOpCode === TextCommandType.CT_GET_PLAIN_STR || textOP.m_iOpCode === TextCommandType.CT_GET_RICH_STR) {
      let resultStr = '';
      const range = this.m_textComp.convertIdUincodesToLetter(textOP.m_fParam2, textOP.m_fParam3);

      if (textOP.m_iOpCode === TextCommandType.CT_GET_PLAIN_STR) {
        resultStr = this.m_textComp.getPlainStr(textOP.m_fParam1, range.x, range.y);
        resultTextOp.m_iOpCode = TextCommandType.CT_GET_PLAIN_STR;
      } else {
        resultStr = this.m_textComp.getRichStr(textOP.m_fParam1, range.x, range.y, textOP.m_fParam4);
        resultTextOp.m_iOpCode = TextCommandType.CT_GET_RICH_STR;
      }

      resultTextOp.m_sParam = resultStr;
    } else if (textOP.m_iOpCode === TextCommandType.CT_GET_CURSOR_RECT) {
      const cursor_rect = this.m_textComp.getCursorRect();
      const canvas_rect = this.m_textComp.canvas.canvasRect;
      const x = cursor_rect.x + (canvas_rect.x + 0.5 * canvas_rect.width);
      const y = cursor_rect.y + (canvas_rect.y + 0.5 * canvas_rect.height);
      cursor_rect.x = x;
      cursor_rect.y = y;
      const sticker_rect = new Rect(-0.5 * this.m_widgetOriginalPixelSize.x, -0.5 * this.m_widgetOriginalPixelSize.y, this.m_widgetOriginalPixelSize.x, this.m_widgetOriginalPixelSize.y);
      const sticker_center = new Amaz$2.Vector2f(0, 0);
      resultTextOp.m_iOpCode = TextCommandType.CT_GET_CURSOR_RECT;
      resultTextOp.m_fParam1 = sticker_rect.width === 0 ? 0 : (cursor_rect.x - sticker_center.x) / (sticker_rect.width * 0.5);
      resultTextOp.m_fParam2 = sticker_rect.height === 0 ? 0 : (cursor_rect.y - sticker_center.y) / (sticker_rect.height * 0.5);
      resultTextOp.m_fParam3 = sticker_rect.width === 0 ? 0 : cursor_rect.width / sticker_rect.width;
      resultTextOp.m_fParam4 = sticker_rect.height === 0 ? 0 : cursor_rect.height / sticker_rect.height;
    } else if (textOP.m_iOpCode === TextCommandType.CT_GET_CHAR_RECT) {
      const letter_id = this.m_textComp.convertIdUToL(textOP.m_fParam1);
      const char_rect = this.m_textComp.getTextRect(letter_id, letter_id);
      const canvas_rect = this.m_textComp.getCanvasCustomizedExpanded();
      const canvas_center = new Amaz$2.Vector2f(canvas_rect.x + canvas_rect.width * 0.5, canvas_rect.y + canvas_rect.height * 0.5);
      resultTextOp.m_iOpCode = TextCommandType.CT_GET_CHAR_RECT;
      resultTextOp.m_fParam1 = canvas_rect.width === 0 ? 0 : (char_rect.x - canvas_center.x) / (canvas_rect.width * 0.5);
      resultTextOp.m_fParam2 = canvas_rect.height === 0 ? 0 : (char_rect.y - canvas_center.y) / (canvas_rect.height * 0.5);
      resultTextOp.m_fParam3 = canvas_rect.width === 0 ? 0 : char_rect.width / canvas_rect.width;
      resultTextOp.m_fParam4 = canvas_rect.height === 0 ? 0 : char_rect.height / canvas_rect.height;
    } else if (textOP.m_iOpCode === TextCommandType.CT_GET_CURSOR_CHAR_INDEX) {
      resultTextOp.m_iOpCode = TextCommandType.CT_GET_CURSOR_CHAR_INDEX;
      const letter_id = this.m_textComp.getLetterIndexByCursor(textOP.m_fParam1);
      let utf16_id = this.m_textComp.convertIdLToU(letter_id);
      const cursor_id = this.m_textComp.getTextEditCursorIndex();

      if (letter_id === 0 && cursor_id == letter_id && textOP.m_fParam1 === -1) {
        utf16_id -= 1;
      } else if (letter_id === this.m_textComp.letters.size() - 1 && cursor_id === letter_id + 1 && textOP.m_fParam1 === 1) {
        utf16_id += 1;
        const last_letter = this.m_textComp.letters.back();

        if (last_letter instanceof Amaz$2.Letter) {
          utf16_id += last_letter.getUTF16Size();
        }
      }

      resultTextOp.m_fParam1 = utf16_id;
    } else if (textOP.m_iOpCode === TextCommandType.CT_GET_SELECT_RANGE) {
      resultTextOp.m_iOpCode = TextCommandType.CT_GET_SELECT_RANGE;
      const ret = this.m_textComp.getSelectRange();
      resultTextOp.m_fParam1 = ret.x;
      resultTextOp.m_fParam2 = this.m_textComp.convertIdLToU(ret.y);
      resultTextOp.m_fParam3 = this.m_textComp.convertIdLToU(ret.z);
    } else if (textOP.m_iOpCode === TextCommandType.CT_GET_ERROR_INFO) {
      resultTextOp.m_iOpCode = TextCommandType.CT_GET_ERROR_INFO;
      resultTextOp.m_fParam1 = this.m_textComp.getEditErrorCode();
      resultTextOp.m_sParam = this.m_textComp.getEditErrorLog();
    } else if (textOP.m_iOpCode === TextCommandType.CT_GET_EDIT_CONTEXT_INFO) {
      resultTextOp.m_iOpCode = TextCommandType.CT_GET_EDIT_CONTEXT_INFO; // ts type change

      resultTextOp.m_fParam1 = this.m_textComp.getTextEditEnable() ? 1 : 0;
      resultTextOp.m_fParam2 = this.m_textComp.convertIdLToU(this.m_textComp.getTextEditCursorIndex());
      resultTextOp.m_fParam3 = this.m_textComp.getTextEditHasSelected() ? 1 : 0;
      resultTextOp.m_fParam4 = this.m_textComp.getTextEditIsInputMethord() ? 1 : 0;
      const range = this.m_textComp.getSelectRange();
      range.y = this.m_textComp.convertIdLToU(range.y);
      range.z = this.m_textComp.convertIdLToU(range.z); // normalize pixel coordinates (of sticker rect)

      const cursor_rect = this.m_textComp.getCursorRect().copy();
      const canvas_rect = this.m_textComp.canvas.canvasRect;
      cursor_rect.x = cursor_rect.x + canvas_rect.x + 0.5 * canvas_rect.width;
      cursor_rect.y = cursor_rect.y + canvas_rect.y + 0.5 * canvas_rect.height;
      const sticker_rect = new Rect(-0.5 * this.m_widgetOriginalPixelSize.x, -0.5 * this.m_widgetOriginalPixelSize.y, this.m_widgetOriginalPixelSize.x, this.m_widgetOriginalPixelSize.x);
      const sticker_center = new Amaz$2.Vector2f(0, 0);
      const x = sticker_rect.width === 0 ? 0 : (cursor_rect.x - sticker_center.x) / (sticker_rect.width * 0.5);
      const y = sticker_rect.height === 0 ? 0 : (cursor_rect.y - sticker_center.y) / (sticker_rect.height * 0.5);
      const width = sticker_rect.width === 0 ? 0 : cursor_rect.width / sticker_rect.width;
      const height = sticker_rect.height === 0 ? 0 : cursor_rect.height / sticker_rect.height;
      const richTextStr = this.m_textComp.getRichStr(0, 0, 0, 0);
      const errorInfoStr = this.m_textComp.getEditErrorLog();
      const jsonObj = {
        selectRange: [range.x, range.y, range.z],
        cursorRect: [x, y, width, height],
        richText: richTextStr,
        errorInfo: errorInfoStr
      };
      const retStr = JSON.stringify(jsonObj);
      resultTextOp.m_sParam = retStr;
    } else if (textOP.m_iOpCode === TextCommandType.CT_GET_SELECT_HANDLE_RECT) {
      resultTextOp.m_iOpCode = TextCommandType.CT_GET_SELECT_HANDLE_RECT;

      if (this.m_textComp.getSelectHandleVisible()) {
        const indexRet = this.m_textComp.getSelectHandleIndex();
        const rectRet = this.m_textComp.getSelectHandleRect();
        const sticker_rect = new Rect(-0.5 * this.m_widgetOriginalPixelSize.x, -0.5 * this.m_widgetOriginalPixelSize.y, this.m_widgetOriginalPixelSize.x, this.m_widgetOriginalPixelSize.y);
        const sticker_center = new Amaz$2.Vector2f(0, 0);
        const canvas_rect = this.m_textComp.canvas.canvasRect;
        const rect_1 = rectRet.get(0);
        const rect_2 = rectRet.get(1);
        let x_1 = 0,
            y_1 = 0,
            width_1 = 0,
            height_1 = 0;
        let x_2 = 0,
            y_2 = 0,
            width_2 = 0,
            height_2 = 0;

        if (rect_1 instanceof Rect) {
          rect_1.x = rect_1.x + canvas_rect.x + 0.5 * canvas_rect.width;
          rect_1.y = rect_1.y + canvas_rect.y + 0.5 * canvas_rect.height;
          x_1 = sticker_rect.width === 0 ? 0 : (rect_1.x - sticker_center.x) / (sticker_rect.width * 0.5);
          y_1 = sticker_rect.height === 0 ? 0 : (rect_1.y - sticker_center.y) / (sticker_rect.height * 0.5);
          width_1 = sticker_rect.width === 0 ? 0 : rect_1.width / sticker_rect.width;
          height_1 = sticker_rect.height === 0 ? 0 : rect_1.height / sticker_rect.height;
        }

        if (rect_2 instanceof Rect) {
          rect_2.x = rect_2.x + canvas_rect.x + 0.5 * canvas_rect.width;
          rect_2.y = rect_2.y + canvas_rect.y + 0.5 * canvas_rect.height;
          x_2 = sticker_rect.width === 0 ? 0 : (rect_2.x - sticker_center.x) / (sticker_rect.width * 0.5);
          y_2 = sticker_rect.height === 0 ? 0 : (rect_2.y - sticker_center.y) / (sticker_rect.height * 0.5);
          width_2 = sticker_rect.width === 0 ? 0 : rect_2.width / sticker_rect.width;
          height_2 = sticker_rect.height === 0 ? 0 : rect_2.height / sticker_rect.height;
        }

        resultTextOp.m_fParam1 = this.m_textComp.convertIdLToU(indexRet.x);
        resultTextOp.m_fParam2 = this.m_textComp.convertIdLToU(indexRet.y);
        const jsonObj = {
          selectHandleRect_0: [x_1, y_1, width_1, height_1],
          selectHandleRect_1: [x_2, y_2, width_2, height_2]
        };
        const retStr = JSON.stringify(jsonObj);
        resultTextOp.m_sParam = retStr;
      }
    }

    return resultTextOp;
  }

  _createTextEntity(scene) {
    const renderEntityName = this.m_name + 'renderEntity';
    this.m_renderEntity = AmazUtils$1.createEntity(renderEntityName, scene);
    this.m_renderEntity.layer = this.m_cameraLayer;
    const localPos = new Vec3(0.0, 0.0, 0.0);
    const scale = new Vec3(1.0, 1.0, 1.0);
    const rotate = new Vec3(0.0, 0.0, 0.0); // add transform component to render entity

    this.m_renderEntity.transform = {
      position: localPos,
      scale: scale,
      rotation: rotate
    };
    this.m_renderEntity.addComponent('Text');
    this.m_renderEntity.addComponent('MeshRenderer');
    this.m_textComp = this.m_renderEntity.getComponent('Text');
    this.createWidgetRootEntity(scene);

    if (null != this.m_rootEntity) {
      AmazUtils$1.addChildEntity(this.m_rootEntity, this.m_renderEntity);
    }
  }

  _updateRichText(configJson) {
    if (!configJson) {
      return;
    }

    if (null !== this.m_textComp) {
      // set rich text
      if ('richText' in configJson) {
        const configRichText = configJson.richText; // for undo redo follow first letter style.

        if (0 === configRichText.length) {
          if (!this.m_textComp.letters.empty()) {
            const firstLetter = this.m_textComp.letters.get(0);

            if (firstLetter instanceof Amaz$2.Letter) {
              this.m_textComp.recordReuseStyle(firstLetter);
            }
          }
        } else {
          this.m_textComp.recordReuseStyle(null);
        }

        this.m_textComp.richStr = configRichText;
      }
    }
  }

  _updateTextLineMaxWidth(screenSize, extralScale) {
    if (this.m_textComp) {
      if (this.m_lineMaxWidth > 0) {
        this.m_textComp.typeSettingParam.wordWrapWidth = extralScale.x === 0 ? 0 : screenSize.x * this.m_lineMaxWidth / extralScale.x;
      } else {
        this.m_textComp.typeSettingParam.wordWrapWidth = 10000000;
      }
    }
  }

  _setTextLineMaxWidth(lineMaxWidth, screenSize, extralScale) {
    this.m_lineMaxWidth = lineMaxWidth;

    this._updateTextLineMaxWidth(screenSize, extralScale);
  }

  _updateRichTextShapeParams(richTextConfig) {
  }

  _updateTextParams(configJson) {
    if (!configJson) {
      return;
    }

    if (null !== this.m_textComp) {
      // set text root path
      {
        if ('rootPath' in configJson) {
          const configRootPath = configJson.rootPath;
          this.m_textComp.rootPath = configRootPath;
        }
      } // set text global alpha

      {
        if ('globalAlpha' in configJson) {
          const configGlobalAlpha = configJson.globalAlpha;
          this.m_textComp.globalAlpha = configGlobalAlpha;
        }

        if ('sdfTextAlpha' in configJson) {
          const configSDFTextAlpha = configJson.sdfTextAlpha;
          this.m_textComp.sdfTextAlpha = configSDFTextAlpha;
        }
      } // set text selected color

      {
        if ('selectedColor' in configJson) {
          const configSelectedColor = AmazUtils$1.CastJsonArray4fToAmazVector4f(configJson.selectedColor);

          if (null !== configSelectedColor) {
            this.m_textComp.selectColor = configSelectedColor;
          } else {
            console.error(TEMPLATE_TAG, '_updateTextParams config json selectedColor is not vector4f!');
          }
        }
      } // set typeSettingKind

      {
        if ('typeSettingKind' in configJson) {
          const configTypeSettingKind = configJson.typeSettingKind; // if need cast number to enum

          this.m_textComp.typeSettingParam.typeSettingKind = configTypeSettingKind;
        } // set typeSettingAlign


        if ('typeSettingAlign' in configJson) {
          const configTypeSettingAlign = configJson.typeSettingAlign; // if need cast number to enum

          this.m_textComp.typeSettingParam.typeSettingAlign = configTypeSettingAlign;
        }

        if ('lineSpacing' in configJson) {
          const configLineSpacing = configJson.lineSpacing; // if need cast number to enum

          this.m_textComp.typeSettingParam.lineSpacing = configLineSpacing;
        }

        if ('letterSpacing' in configJson) {
          const configLetterSpacing = configJson.letterSpacing;
          this.m_textComp.typeSettingParam.letterSpacing = configLetterSpacing;
        }

        if ('innerPadding' in configJson) {
          const configLetterSpacing = configJson.innerPadding;
          this.m_textComp.typeSettingParam.horizontalPadding = configLetterSpacing;
          this.m_textComp.typeSettingParam.verticalPadding = configLetterSpacing;
        }

        if ('lineMaxWidth' in configJson) {
          // TODO: need m_screen size update logic
          const configLineMaxWidth = configJson.lineMaxWidth;

          if (this.widgetResolutionType === WidgetResolutionType.NORMALIZED) {
            const normalizedScale = this.getTextureNormalizedScale();

            this._setTextLineMaxWidth(configLineMaxWidth, this.m_screenSize, normalizedScale);
          } else if (this.widgetResolutionType === WidgetResolutionType.ORIGINAL) {
            const extralScale = new Amaz$2.Vector2f(1.0, 1.0);

            if (this.m_textInfoLayerWidth > 0) {
              const screenSize = new Amaz$2.Vector2f(this.m_textInfoLayerWidth, this.m_textInfoLayerWidth);

              this._setTextLineMaxWidth(configLineMaxWidth, screenSize, extralScale);
            } else {
              this._setTextLineMaxWidth(configLineMaxWidth, this.m_screenSize, extralScale);
            }
          } else if (this.widgetResolutionType === WidgetResolutionType.DESIGN_HEIGHT) {
            // TODO: if need using extral property record design height mode
            // scale
            const extralScale = new Amaz$2.Vector2f(this.m_extralScale.x, this.m_extralScale.y);

            this._setTextLineMaxWidth(configLineMaxWidth, this.m_screenSize, extralScale);
          } else {
            const extralScale = new Amaz$2.Vector2f(this.m_extralScale.x, this.m_extralScale.y);

            this._setTextLineMaxWidth(configLineMaxWidth, this.m_screenSize, extralScale);
          }
        }

        if ('oneLineCutOff' in configJson) {
          const configFlag = configJson.oneLineCutOff;

          if (configFlag) {
            this.m_textComp.typeSettingParam.lineBreakType = Amaz$2.LineBreakType.CUT_OFF;
          } else {
            this.m_textComp.typeSettingParam.lineBreakType = Amaz$2.LineBreakType.AUTO_LINEBREAK;
          }
        }

        if ('cutOffPostfix' in configJson) {
          const configCutOffPostfix = configJson.cutOffPostfix;
          this.m_textComp.cutOffPostfix = configCutOffPostfix;
        }

        if ('autoAdaptDpiEnabled' in configJson) {
          const configAutoAdaptDpiEnabled = configJson.autoAdaptDpiEnabled;
          this.m_textComp.typeSettingParam.autoAdaptDpiEnabled = configAutoAdaptDpiEnabled;
        }
      } // set canvas

      {
        if ('canvas' in configJson) {
          const configCanvas = configJson.canvas; // if need cast number to enum

          this.m_textComp.canvas.canvasEnabled = configCanvas;
        }

        if ('canvasColor' in configJson) {
          const configCanvasColor = AmazUtils$1.CastJsonArray4fToAmazVector4f(configJson.canvasColor);

          if (null !== configCanvasColor) {
            this.m_textComp.canvas.canvasColor = configCanvasColor;
          } else {
            console.error(TEMPLATE_TAG, '_updateTextParams config json canvasColor is not vector4f!');
          }
        }

        if ('canvasRoundCorner' in configJson) {
          const configCanvasRoundCorner = configJson.canvasRoundCorner;
          this.m_textComp.canvas.canvasRoundCornerEnabled = configCanvasRoundCorner;
        }

        if ('canvasRoundRadius' in configJson) {
          const configCanvasRoundRadius = configJson.canvasRoundRadius;
          this.m_textComp.canvas.canvasRoundRadius = configCanvasRoundRadius;
        }

        if ('canvasRoundRadiusScale' in configJson) {
          const configCanvasRoundRadiusScale = configJson.canvasRoundRadiusScale;
          this.m_textComp.canvas.canvasRoundRadiusScale = configCanvasRoundRadiusScale;
        }

        if ('canvasWrapped' in configJson) {
          const configCanvasWrapped = configJson.canvasWrapped;
          this.m_textComp.canvas.canvasWrappText = configCanvasWrapped;
        }

        if ('canvasSplitThreshold' in configJson) {
          const configCanvasSplitThreshold = configJson.canvasSplitThreshold;
          this.m_textComp.canvas.canvasSplitThreshold = configCanvasSplitThreshold;
        }

        if ('canvasSplitPadding' in configJson) {
          const configCanvasSplitPadding = configJson.canvasSplitPadding;
          this.m_textComp.canvas.canvasSplitPadding = configCanvasSplitPadding;
        }

        if ('canvasCustomized' in configJson) {
          const configCanvasCustomized = configJson.canvasCustomized;
          this.m_textComp.canvas.canvasCustomizedEnabled = configCanvasCustomized;
        }

        if ('canvasWHCustomized' in configJson) {
          const configCanvasWHCustomized = AmazUtils$1.CastJsonArray2fToAmazVector2f(configJson.canvasWHCustomized);

          if (null !== configCanvasWHCustomized) {
            this.m_textComp.canvas.canvasWHCustomized = configCanvasWHCustomized;
          } else {
            console.error(TEMPLATE_TAG, '_updateTextParams config json canvasWHCustomized is not vector2f!');
          }
        }

        if ('canvasOffsetCustomized' in configJson) {
          const configCanvasOffsetCustomized = AmazUtils$1.CastJsonArray2fToAmazVector2f(configJson.canvasOffsetCustomized);

          if (null !== configCanvasOffsetCustomized) {
            this.m_textComp.canvas.canvasOffsetCustomized = configCanvasOffsetCustomized;
          } else {
            console.error(TEMPLATE_TAG, '_updateTextParams config json canvasOffsetCustomized is not vector2f!');
          }
        }
      } // set text style

      {
        if ('italicDegree' in configJson) {
          const configItalicDegree = configJson.italicDegree;
          this.m_textComp.activeTextStyle.italicAngle = configItalicDegree;
        }

        if ('boldValue' in configJson) {
          const configBoldValue = configJson.boldValue;
          this.m_textComp.activeTextStyle.boldValue = configBoldValue;
        }

        if ('decorationWidth' in configJson) {
          const configDecorationWidth = configJson.decorationWidth;
          this.m_textComp.activeTextStyle.decorationWidth = configDecorationWidth;
        }

        if ('decorationOffset' in configJson) {
          const configDecorationOffset = configJson.decorationOffset;
          this.m_textComp.activeTextStyle.decorationOffset = configDecorationOffset;
        }

        if ('fallbackFontPathList' in configJson) {
          const configFontPaths = AmazUtils$1.CastJsonArrayToAmazVector(configJson.fallbackFontPathList);
          this.m_textComp.fallbackFontPaths = configFontPaths;
        }
      } // update KTV animation parameters

      {
        if ('ktvColor' in configJson) {
          const configKTVColor = AmazUtils$1.CastJsonArray4fToAmazVector4f(configJson.ktvColor);

          if (null !== configKTVColor) {
            this.m_ktvColor = configKTVColor;
            const configKTVColorVec = AmazUtils$1.CastJsonArrayToAmazVector(configJson.ktvColor);
            this.m_scriptPassthroughParams.set('ktvColor', configKTVColorVec);
            this.m_scriptPassthroughParams.set('sdfTextDirty', true);
            this.m_scriptPassthroughParamsDirty = true;
          } else {
            console.error(TEMPLATE_TAG, '_updateTextParams config json ktvColor is not vector4f!');
          }
        }

        if ('ktvOutlineColor' in configJson) {
          const configKTVOutlineColor = AmazUtils$1.CastJsonArray4fToAmazVector4f(configJson.ktvOutlineColor);

          if (null !== configKTVOutlineColor) {
            this.m_ktvOutlineColor = configKTVOutlineColor;
            const configKTVOutlineColorVec = AmazUtils$1.CastJsonArrayToAmazVector(configJson.ktvOutlineColor);
            this.m_scriptPassthroughParams.set('ktvOutlineColor', configKTVOutlineColorVec);
            this.m_scriptPassthroughParams.set('sdfTextDirty', true);
            this.m_scriptPassthroughParamsDirty = true;
          } else {
            console.error(TEMPLATE_TAG, '_updateTextParams config json ktvOutlineColor is not vector4f!');
          }
        }

        if ('ktvShadowColor' in configJson) {
          const configKTVShadowColor = AmazUtils$1.CastJsonArray4fToAmazVector4f(configJson.ktvShadowColor);

          if (null !== configKTVShadowColor) {
            this.m_ktvShadowColor = configKTVShadowColor;
            const configKTVShadowColorVec = AmazUtils$1.CastJsonArrayToAmazVector(configJson.ktvShadowColor);
            this.m_scriptPassthroughParams.set('ktvShadowColor', configKTVShadowColorVec);
            this.m_scriptPassthroughParams.set('sdfTextDirty', true);
            this.m_scriptPassthroughParamsDirty = true;
          } else {
            console.error(TEMPLATE_TAG, '_updateTextParams config json ktvShadowColor is not vector4f!');
          }
        }
      } // TODO: update Text Shape

      {
        //  Text Shape will not using in text template
        let textShapeConfig = '';

        if ('textShape' in configJson) {
          textShapeConfig = configJson.textShape;
        }

        if (textShapeConfig !== '') {
          this._updateRichTextShapeParams(configJson);
        } else {
          const letterPosChanged = this.m_textComp.typeSettingDirty;
          this.m_textComp.forceTypeSetting();
          const rect = this.m_textComp.getCanvasCustomizedExpanded();
          const pixelSize = new Vec2(rect.width, rect.height);
          this.updateOriginaSize(pixelSize, this.m_screenSize);

          if (letterPosChanged) {
            this.reloadAllAnimation();
          }
        }
      }
    } else {
      console.error(TEMPLATE_TAG, '_updateTextComp text componet is null!');
    }
  }

  updateText() {
    if (this.m_needUpdateTextCom) {
      if (!this.m_jsonPares) {
        console.error(TEMPLATE_TAG, '_updateTextComp config json is empty!');
        return;
      } else if ('rich_text_edit' in this.m_jsonPares) {
        const richTextEditConfig = this.m_jsonPares.rich_text_edit;
        const textOP = {
          m_iOpCode: richTextEditConfig.op_code,
          m_fParam1: richTextEditConfig.fparam1,
          m_fParam2: richTextEditConfig.fparam2,
          m_fParam3: richTextEditConfig.fparam3,
          m_fParam4: richTextEditConfig.fparam4,
          m_sParam: richTextEditConfig.sparam
        };
        this.setRichTextByOPCode(textOP, false);
      } else {
        let configJson = null;

        if ('text_params' in this.m_jsonPares) {
          configJson = this.m_jsonPares.text_params;
        }

        this._updateRichText(configJson);

        this._updateTextParams(configJson);
      }

      this.m_needUpdateTextCom = false;
    }
  }

  onUpdate(timeStamp) {
    if (!this.m_enable || !this.checkIsInRange(timeStamp)) {
      //if out of time range and then UI check visible, so need first update and then set visible false.
      super.onUpdate(timeStamp);

      if (this.m_rootEntity && this.m_rootEntity.visible) {
        this.m_rootEntity.visible = false;
        this.resetAllAnimation();
      }

      return;
    } else {
      if (this.m_rootEntity && !this.m_rootEntity.visible) {
        this.m_rootEntity.visible = true;
      }

      super.onUpdate(timeStamp);
      this.seekAnimations(timeStamp);
    }
  }

}

/**
 * @module
 * @category Segment
 * @name Segment
 * @interfacedesc A Segment module provides capabilities for create layers like text layer, sprite layer, vectogram layer, etc.
 * @description Constructor to create a Head instance.
 * @sdk 12.2.0
 */

var ScriptSegment;

(function (ScriptSegment) {
  /**
   * @function
   * @name CreateWidget
   * @description Create a new Widget and add it to scene.
   * @param {string} name - Name of the Widget to add.
   * @param {any} jsonParam - json parameters of the Widget to add.
   * @param {WidgetType} widgetType - Type of the Widget to add.
   * @param {Scene} scene - Add the create widget to scene.
   * @return {Widget | RichText | Sprite | Shape | null} if create successfully return widget, otherwise return null.
   * @sdk 12.2.0
   */
  function CreateWidget(name, jsonParam, widgetType, scene) {
    let widget = null;

    if (jsonParam) {
      if (widgetType === WidgetType.ROOT) {
        widget = new Widget(name, widgetType, scene);
        widget.parameters = jsonParam;
        widget.createWidgetRootEntity(scene);
      } else if (widgetType === WidgetType.SPRITE) {
        widget = new Sprite(name, widgetType, scene, jsonParam);
      } else if (widgetType === WidgetType.SHAPE) {
        widget = new Shape(name, widgetType, scene);
        widget.createShape(jsonParam, scene);
      } else if (widgetType === WidgetType.TEXT) {
        widget = new RichText(name, widgetType, scene);
        widget.createRichText(jsonParam, scene);
      }
    } else {
      console.error(TEMPLATE_TAG, 'create widget error, jsonParam is null or undefined!');
    }

    return widget;
  }

  ScriptSegment.CreateWidget = CreateWidget;
  /**
   * @function
   * @name RemoveWidget
   * @description remove a widget root entity from scene.
   * @param {Widget} widget - current wifget.
   * @param {Scene} scene - Remove widget from this scene.
   * @return {boolean} if remove successfully return true, otherwise return false.
   * @sdk 12.2.0
   */

  function RemoveWidget(widget, scene) {
    widget.removeWidgetRootEntity(scene);
    return true;
  }

  ScriptSegment.RemoveWidget = RemoveWidget;
  /**
   * @function
   * @name GetWidgetName
   * @description: get current widget name
   * @param {Widget} widget - current widget
   * @return {string} widget name
   */

  function GetWidgetName(widget) {
    return widget.widgetName;
  }

  ScriptSegment.GetWidgetName = GetWidgetName;

  function SetResolutionType(widget, resolutionType) {
    widget.widgetResolutionType = resolutionType;
  }

  ScriptSegment.SetResolutionType = SetResolutionType;

  function GetResolutionType(widget) {
    return widget.widgetResolutionType;
  }

  ScriptSegment.GetResolutionType = GetResolutionType;

  function OnResize(widget, screenSize, pixelRatio, extralScale) {
    widget.onResize(screenSize, pixelRatio, extralScale);
  }

  ScriptSegment.OnResize = OnResize;

  function AddToRootWidget(rootwidget, renderWidget) {
    const renderWidgetEntity = renderWidget.rootEntity;
    const rootWidgetEntity = rootwidget.rootEntity;

    if (renderWidgetEntity && rootWidgetEntity) {
      AmazUtils$1.addChildEntity(rootWidgetEntity, renderWidgetEntity);
    }
  }

  ScriptSegment.AddToRootWidget = AddToRootWidget;

  function RemoveFromRootWidget(rootwidget, renderWidget) {
    var _a;

    const renderWidgetEntity = renderWidget.rootEntity;
    const rootWidgetEntity = rootwidget.rootEntity;

    if (renderWidgetEntity && rootWidgetEntity) {
      AmazUtils$1.removeChildEntity(rootWidgetEntity, renderWidgetEntity);
      (_a = renderWidget.scene) === null || _a === void 0 ? void 0 : _a.removeEntity(renderWidgetEntity);
    }
  }

  ScriptSegment.RemoveFromRootWidget = RemoveFromRootWidget;
  /**
   * @function
   * @name SetWidgetPosition
   * @description set widget position.
   * @param {Widget} widget - current wifget.
   * @param {Vec3} position - new position for widget.
   * @sdk 12.2.0
   */

  function SetWidgetPosition(widget, position) {
    widget.position = position;
  }

  ScriptSegment.SetWidgetPosition = SetWidgetPosition;
  /**
   * @function
   * @name GetWidgetPosition
   * @description get a widget position.
   * @param {Widget} widget - current wifget.
   * @return {Vec3} widget current position.
   * @sdk 12.2.0
   */

  function GetWidgetPosition(widget) {
    return widget.position;
  }

  ScriptSegment.GetWidgetPosition = GetWidgetPosition;
  /**
   * @function
   * @name SetWidgetScale
   * @description set widget position.
   * @param {Widget} widget - current wifget.
   * @param {Vec3} scale - new scale for widget.
   * @sdk 12.2.0
   */

  function SetWidgetScale(widget, scale) {
    widget.scale = scale;
  }

  ScriptSegment.SetWidgetScale = SetWidgetScale;
  /**
   * @function
   * @name GetWidgetScale
   * @description get a widget scale.
   * @param {Widget} widget - current wifget.
   * @return {Vec3} widget current scale.
   * @sdk 12.2.0
   */

  function GetWidgetScale(widget) {
    return widget.scale;
  }

  ScriptSegment.GetWidgetScale = GetWidgetScale;
  /**
   * @function
   * @name SetWidgetRotation
   * @description set widget rotation.
   * @param {Widget} widget - current wifget.
   * @param {Vec3} rotation - new rotation for widget.
   * @sdk 12.2.0
   */

  function SetWidgetRotation(widget, rotation) {
    widget.rotation = rotation;
  }

  ScriptSegment.SetWidgetRotation = SetWidgetRotation;
  /**
   * @function
   * @name GetWidgetRotation
   * @description get a widget rotation.
   * @param {Widget} widget - current wifget.
   * @return {Vec3} widget current rotation.
   * @sdk 12.2.0
   */

  function GetWidgetRotation(widget) {
    return widget.rotation;
  }

  ScriptSegment.GetWidgetRotation = GetWidgetRotation;

  function GetWidgetDuration(widget) {
    return widget.duration;
  }

  ScriptSegment.GetWidgetDuration = GetWidgetDuration;
  /**
   * @function
   * @name SetWidgetLayer
   * @description set widget render layer.
   * @param {Widget} widget - current wifget.
   * @param {number} layer - render layer for widget.
   * @sdk 12.2.0
   */

  function SetWidgetLayer(widget, layer) {
    widget.layer = layer;
  }

  ScriptSegment.SetWidgetLayer = SetWidgetLayer;
  /**
   * @function
   * @name GetWidgetRotation
   * @description get a widget rotation.
   * @param {Widget} widget - current wifget.
   * @return {Vec3} widget current rotation.
   * @sdk 12.2.0
   */

  function GetWidgetLayer(widget) {
    return widget.layer;
  }

  ScriptSegment.GetWidgetLayer = GetWidgetLayer;
  /**
   * @function
   * @name SetWidgetLocalOrderInLayer
   * @description: set a widget loacl order in layer
   * @param {Widget} widget - current widget
   * @param {number} order - local order in layer
   * @return {void}
   */

  function SetWidgetLocalOrderInLayer(widget, order) {
    widget.localOrder = order;
  }

  ScriptSegment.SetWidgetLocalOrderInLayer = SetWidgetLocalOrderInLayer;

  function SetWidgetTimeRange(widget, startTime, endTime) {
    widget.setTimeRange(startTime, endTime);
  }

  ScriptSegment.SetWidgetTimeRange = SetWidgetTimeRange;

  function SetWidgetSegmentTimeRange(widget, startTime, endTime, initTemplateDuration) {
    widget.setSegmentTimeRange(startTime, endTime, initTemplateDuration);
  }

  ScriptSegment.SetWidgetSegmentTimeRange = SetWidgetSegmentTimeRange;
  /**
   * @function
   * @name UpdateWidgetRootEntity
   * @description: update current widget root entity parameters
   * @param {Widget} widget - current widget
   * @return {void}
   */

  function UpdateWidgetRootEntity(widget) {
    widget.updateRootEntityParam();
  }

  ScriptSegment.UpdateWidgetRootEntity = UpdateWidgetRootEntity;

  function OnUpdate(widget, timeStamp) {
    widget.onUpdate(timeStamp);
  }

  ScriptSegment.OnUpdate = OnUpdate;

  function GetWidgetBindingBox(widget) {
    return widget.bindingBox;
  }

  ScriptSegment.GetWidgetBindingBox = GetWidgetBindingBox;

  function SetWidgetEnable(widget, enable) {
    widget.enable = enable;
  }

  ScriptSegment.SetWidgetEnable = SetWidgetEnable;
  /**
   * @function
   * @name SetWidgetParams
   * @description: set sprite/shape/text widget parameters.
   * @param {Widget | Sprite | Shape | RichText} widget - current widget.
   * @param {any} jsonParam - current parameters by json object.
   * @return {boolean} if set successfully return true, otherwise return false.
   */

  function SetWidgetParams(widget, jsonParam) {
    widget.parameters = jsonParam;
    return true;
  }

  ScriptSegment.SetWidgetParams = SetWidgetParams;
  /**
   * @function
   * @name GetWidgetParams
   * @description: get sprite/shape/text widget parameters by josn
   * @param {Spr Sprite | Shape | Textite} widget - current widget
   * @return {string} return parameters by json string.
   */

  function GetWidgetParams(widget) {
    return widget.parameters;
  }

  ScriptSegment.GetWidgetParams = GetWidgetParams;
  /**
   * @function
   * @name SetRichTextParams
   * @description: eidte rich text by op code.
   * @param {RichText} widget - current widget
   * @param {number} iOpcode - op code.
   * @param {number} fParam1 - float parameter.
   * @param {number} fParam2 - float parameter.
   * @param {number} fParam3 - float parameter.
   * @param {number} fParam4 - float parameter.
   * @param {string} sParam - json string parameter.
   * @param {bigint} isSync - if true, text will force flush command.
   * @return {void}
   */

  function SetRichTextParams(widget, iOpcode, fParam1, fParam2, fParam3, fParam4, sParam, isSync) {
    const textOP = {
      m_iOpCode: iOpcode,
      m_fParam1: fParam1,
      m_fParam2: fParam2,
      m_fParam3: fParam3,
      m_fParam4: fParam4,
      m_sParam: sParam
    };
    widget.setRichTextByOPCode(textOP, isSync);
  }

  ScriptSegment.SetRichTextParams = SetRichTextParams;
  /**
   * @function
   * @name GetRichTextParams
   * @description: eidte rich text by op code.
   * @param {RichText} widget - current widget
   * @param {number} iOpcode - op code.
   * @param {number} fParam1 - float parameter.
   * @param {number} fParam2 - float parameter.
   * @param {number} fParam3 - float parameter.
   * @param {number} fParam4 - float parameter.
   * @param {string} sParam - json string parameter.
   * @return {voTextOPStructid} - return edite result by op code struct.
   */

  function GetRichTextParams(widget, iOpcode, fParam1, fParam2, fParam3, fParam4, sParam) {
    const textOP = {
      m_iOpCode: iOpcode,
      m_fParam1: fParam1,
      m_fParam2: fParam2,
      m_fParam3: fParam3,
      m_fParam4: fParam4,
      m_sParam: sParam
    };
    return widget.getRichTextByOPCode(textOP);
  }

  ScriptSegment.GetRichTextParams = GetRichTextParams;

  function SetWidgetAnimation(widget, path, resourceID, scriptType, animaType, startTime, duration, loopDuration) {
    return widget.setWidgetAnimation(path, resourceID, scriptType, startTime, duration, loopDuration, animaType);
  }

  ScriptSegment.SetWidgetAnimation = SetWidgetAnimation;
})(ScriptSegment || (ScriptSegment = {}));

var Amaz$1 = effect.Amaz;
const DEGSIN_SIZE = new Amaz$1.Vector2f(720, 1280);
const SDK_VERSION = '13.1.0';
const SCRIPT_VERSION = '1.0.0';
class TemplateUtils {
  /**
   * desc
   * @date 2022-07-08
   * @param {data: object[]} data
   * @param {scene: Scene} scene
   * @returns { (Widget | null)[]}
   */
  static createChildren(data, scene, screenSize) {
    return data.map(childData => {
      const node = TemplateConfigParser.parseChildNode(childData);
      if (node == null) return null;
      const widgetName = node.name;
      let widget = null;

      if ((node === null || node === void 0 ? void 0 : node.type) === 'sticker') {
        widget = ScriptSegment.CreateWidget(widgetName, node, WidgetType.SPRITE, scene);
      } else if ((node === null || node === void 0 ? void 0 : node.type) === 'text') {
        widget = ScriptSegment.CreateWidget(widgetName, node, WidgetType.TEXT, scene);
      } else if ((node === null || node === void 0 ? void 0 : node.type) === 'shape') {
        widget = ScriptSegment.CreateWidget(widgetName, node, WidgetType.SHAPE, scene);
      }

      if (widget && screenSize.length === 2) {
        const screenSizeVec = new Amaz$1.Vector2f(screenSize[0], screenSize[1]);
        const pixelRatio = 0.5 * screenSize[1];
        const extralScale = new Amaz$1.Vector3f(1.0, 1.0, 1.0);
        ScriptSegment.OnResize(widget, screenSizeVec, pixelRatio, extralScale);
      }

      return widget;
    }).filter(v => v != null);
  }

  static createLayer(_layerName, layerParam, segmentStartTime, segmentEndTime, initTemplateDuration, screenWidth, screenHeight, options) {
    const jsonParam = JSON.parse(layerParam);

    if (options.mainScene != null && options.rootWidget) {
      const [widget] = TemplateUtils.createChildren([jsonParam], options.mainScene, [screenWidth, screenHeight]);

      if (widget != null) {
        if (options.rootWidget) {
          ScriptSegment.AddToRootWidget(options.rootWidget, widget);
        }

        ScriptSegment.SetWidgetSegmentTimeRange(widget, segmentStartTime, segmentEndTime, initTemplateDuration);
        return widget;
      }
    }

    return null;
  }

  static removeLayer(layerNamem, mainScene, rootWidget, renderWidgets) {
    return renderWidgets.filter(value => {
      if (null !== value && undefined !== mainScene && undefined !== rootWidget) {
        if (layerNamem === ScriptSegment.GetWidgetName(value)) {
          ScriptSegment.RemoveWidget(value, mainScene); //ScriptSegment.RemoveFromRootWidget(options.rootWidget, value);

          return false;
        }
      }

      return true;
    });
  }

  static setTemplateTimeRange(startTime, endTime, options) {
    if (undefined !== options.rootWidget && null !== options.rootWidget && undefined !== options.mainScene) {
      ScriptSegment.SetWidgetTimeRange(options.rootWidget, startTime, endTime); //this update logic is instead by custom setting
      // if (undefined !== options.renderWidgets) {
      //   options.renderWidgets.map(value => {
      //     if (null !== value) {
      //       ScriptSegment.SetWidgetSegmentTimeRange(
      //         value,
      //         startTime,
      //         endTime,
      //         initTemplateDuration
      //       );
      //       ScriptSegment.UpdateWidgetAnimationTimeRange(value);
      //     }
      //   });
      // }
    }
  }

  static replaceDependentResource(config, depends) {
    const utils = new Amaz$1.SwingTemplateUtils();
    return utils.replaceDependResource(config, depends);
  }
  /**
   * desc
   * @date 2022-07-08
   * @param {config: string} config
   * @param {scene: Scene} scene
   * @returns { [Widget, (Widget | null)[]] | undefined}
   */


  static constructWidgetsFromConfig(config, depends, scene, screenSize, resolutionType) {
    if (config != null && depends != null && depends.length !== 0) {
      config = TemplateUtils.replaceDependentResource(config, depends);
    }

    const data = TemplateConfigParser.parseConfig(config); // create root widget

    let root = undefined;

    if (data != null) {
      root = ScriptSegment.CreateWidget('rootWidget', data.root, WidgetType.ROOT, scene);
    } else {
      console.error(TEMPLATE_TAG, 'create root widgent error, causeof data parse error', config);
    }

    if (root && screenSize.length === 2) {
      ScriptSegment.SetResolutionType(root, resolutionType);
      const screenSizeVec = new Amaz$1.Vector2f(screenSize[0], screenSize[1]);
      const pixelRatio = 0.5 * screenSize[1];
      let extralScale = new Amaz$1.Vector3f(1.0, 1.0, 1.0);

      if (WidgetResolutionType.DESIGN === resolutionType) {
        const scale = screenSize[0] / DEGSIN_SIZE.x;
        extralScale = new Amaz$1.Vector3f(scale, scale, 1.0);
      } else if (WidgetResolutionType.DESIGN_HEIGHT === resolutionType) {
        const scale = screenSize[1] / DEGSIN_SIZE.y;
        extralScale = new Amaz$1.Vector3f(scale, scale, 1.0);
      }

      ScriptSegment.OnResize(root, screenSizeVec, pixelRatio, extralScale);
    }

    if ((data === null || data === void 0 ? void 0 : data.children) != null && root != null) {
      // create child widget
      const children = TemplateUtils.createChildren(data.children, scene, screenSize);
      children.map(value => {
        if (value !== null && root) {
          ScriptSegment.AddToRootWidget(root, value);
        }
      });
      return [root, children];
    }

    return root ? [root, []] : undefined;
  }
  /**
   * desc
   * @date 2022-07-08
   * @param {_root: Widget | undefined} _root
   * @param {_widgets: (Widget | null)[] | undefined} _widgets
   * @param {_params: string} _params
   */


  static updateWidgetParams(_root, _widgets, _params) {
    const jsonParam = JSON.parse(_params);
    let rootLayer = -1;

    if ('root' in jsonParam) {
      if (_root) {
        const rootJosnOBject = jsonParam.root;
        ScriptSegment.SetWidgetParams(_root, rootJosnOBject);

        if (rootJosnOBject && 'layer' in rootJosnOBject) {
          rootLayer = rootJosnOBject.layer;
        }
      }
    }

    if ('children' in jsonParam) {
      const widgetListParam = jsonParam.children;

      if (widgetListParam instanceof Array) {
        for (let i = 0; i < widgetListParam.length; i++) {
          const widgetParam = widgetListParam[i];

          if (widgetParam && 'name' in widgetParam) {
            const widgetName = widgetParam.name;

            if (_widgets !== undefined) {
              _widgets.map(value => {
                if (null !== value && ScriptSegment.GetWidgetName(value) === widgetName) {
                  if (rootLayer !== -1) {
                    ScriptSegment.SetWidgetLayer(value, rootLayer);
                  }

                  ScriptSegment.SetWidgetParams(value, widgetParam);
                }
              });
            }
          }
        }
      }
    }
  }

  static getRootWidgetDuration(_root) {
    if (_root) {
      return ScriptSegment.GetWidgetDuration(_root);
    } else {
      console.error(TEMPLATE_TAG, 'getRootWidgetDuration: root widget is null');
      return 0;
    }
  }

  static setRootWidgetResolutionType(_root, resolutionType, screen_width, screen_heght) {
    if (_root) {
      ScriptSegment.SetResolutionType(_root, resolutionType);
      const pixelRatio = 0.5 * screen_heght;
      let extralScale = new Amaz$1.Vector3f(1.0, 1.0, 1.0);

      if (WidgetResolutionType.DESIGN === resolutionType) {
        const scale = screen_width / DEGSIN_SIZE.x;
        extralScale = new Amaz$1.Vector3f(scale, scale, 1.0);
      } else if (WidgetResolutionType.DESIGN_HEIGHT === resolutionType) {
        const scale = screen_heght / DEGSIN_SIZE.y;
        extralScale = new Amaz$1.Vector3f(scale, scale, 1.0);
      }

      const screenSizeVec = new Amaz$1.Vector2f(screen_width, screen_heght);
      ScriptSegment.OnResize(_root, screenSizeVec, pixelRatio, extralScale);
    }
  }

  static setWidgetScreenSize(_root, _widgets, screenWidth, screenHeight) {
    const pixelRatio = 0.5 * screenHeight;
    let extralScale = new Amaz$1.Vector3f(1.0, 1.0, 1.0);
    const screenSizeVec = new Amaz$1.Vector2f(screenWidth, screenHeight);

    if (_root) {
      const resolutionType = ScriptSegment.GetResolutionType(_root);

      if (WidgetResolutionType.DESIGN === resolutionType) {
        const scale = screenWidth / DEGSIN_SIZE.x;
        extralScale = new Amaz$1.Vector3f(scale, scale, 1.0);
      } else if (WidgetResolutionType.DESIGN_HEIGHT === resolutionType) {
        const scale = screenHeight / DEGSIN_SIZE.y;
        extralScale = new Amaz$1.Vector3f(scale, scale, 1.0);
      }

      ScriptSegment.OnResize(_root, screenSizeVec, pixelRatio, extralScale);
    }

    const widgetScale = new Amaz$1.Vector3f(1.0, 1.0, 1.0);

    if (_widgets !== undefined) {
      _widgets.map(value => {
        if (null !== value) {
          ScriptSegment.OnResize(value, screenSizeVec, pixelRatio, widgetScale);
        }
      });
    }
  }

  static getWidgetParams(_root, _widgets, _params) {
    const jsonParam = JSON.parse(_params);

    if ('get_all_properties' in jsonParam) {
      if (jsonParam.get_all_properties === true) {
        const outParam = this.getAllWidgetParams(_root, _widgets);
        const retStr = JSON.stringify(outParam);
        return retStr;
      }
    }

    if ('get_sdk_version' in jsonParam && jsonParam.get_sdk_version === true) {
      const sdk_version = {
        sdk_version: SDK_VERSION,
        script_version: SCRIPT_VERSION
      };
      const retStr = JSON.stringify(sdk_version);
      return retStr;
    }

    if ('root' in jsonParam) {
      if (_root) {
        jsonParam.root = this.getRootWidgetParams(_root);
      }
    }

    if ('children' in jsonParam) {
      const widgetListParam = jsonParam.children;

      if (widgetListParam instanceof Array) {
        for (let i = 0; i < widgetListParam.length; i++) {
          const widgetParam = widgetListParam[i];

          if (widgetParam && 'name' in widgetParam) {
            const widgetName = widgetParam.name;

            if (_widgets !== undefined) {
              _widgets.map(value => {
                if (null !== value && ScriptSegment.GetWidgetName(value) === widgetName) {
                  jsonParam.children[i] = this.getOneWidgetParams(value, widgetParam);
                }
              });
            }
          }
        }
      }
    }

    const retStr = JSON.stringify(jsonParam);
    return retStr;
  }

  static getAllWidgetParams(_root, _widgets) {
    const jsonParam = {};
    jsonParam.type = 'ScriptTemplate';

    if (_root) {
      jsonParam.root = this.getRootWidgetParams(_root);
    }

    const children = [];

    if (_widgets !== undefined) {
      for (let i = 0; i < _widgets.length; ++i) {
        const widget = _widgets[i];

        if (widget) {
          const widgetParam = this.getOneWidgetParams(widget, null);
          children.push(widgetParam);
        }
      }
    }

    jsonParam.children = children;
    return jsonParam;
  }

  static getOneWidgetParams(_widget, _widgetParam) {
    if (_widget !== undefined) {
      if (_widget.widgetType === WidgetType.TEXT) {
        return this.getTextWidgetParams(_widget, _widgetParam);
      } else if (_widget.widgetType === WidgetType.SPRITE) {
        return this.getSpriteWidgetParams(_widget);
      } else if (_widget.widgetType === WidgetType.SHAPE) {
        return this.getShapeWidgetParams(_widget);
      }
    }

    return {};
  }

  static getRootWidgetParams(_widget) {
    const outParam = _widget.parameters;
    delete outParam.layout_params;
    delete outParam.order_in_layer;
    return outParam;
  }

  static getTextWidgetParams(_widget, _widgetParam) {
    let outParam = _widgetParam;

    if (_widgetParam && 'rich_text_edit' in _widgetParam) {
      const textEditParam = _widgetParam.rich_text_edit;
      const textOPRet = ScriptSegment.GetRichTextParams(_widget, textEditParam.op_code, textEditParam.fparam1, textEditParam.fparam2, textEditParam.fparam3, textEditParam.fparam4, textEditParam.sparam);
      const resultTextOP = {
        op_code: textOPRet.m_iOpCode,
        fparam1: textOPRet.m_fParam1,
        fparam2: textOPRet.m_fParam2,
        fparam3: textOPRet.m_fParam3,
        fparam4: textOPRet.m_fParam4,
        sparam: textOPRet.m_sParam
      };
      outParam['text_get_command_result'] = resultTextOP;
    } else {
      outParam = _widget.parameters;
      delete outParam.layout_params;
    }

    return outParam;
  }

  static getSpriteWidgetParams(_widget) {
    const outParam = _widget.parameters;
    delete outParam.layout_params;
    delete outParam.visible;
    return outParam;
  }

  static getShapeWidgetParams(_widget) {
    const outParam = _widget.parameters;
    delete outParam.layout_params;
    return outParam;
  }

}

var TemplateEventType;

(function (TemplateEventType) {
  TemplateEventType[TemplateEventType["layerOperation"] = 10100] = "layerOperation";
})(TemplateEventType || (TemplateEventType = {}));

var Amaz = effect.Amaz;
class Main {
  constructor() {
    this.name = 'Main';
    this.scene = undefined;
    this.rootWidget = undefined;
    this.renderWidgets = undefined;
    this.initTemplateDuration = 3;
    this.sceneRef = undefined;
    this.sceneConfig = undefined;
  } // eslint-disable-next-line @typescript-eslint/no-unused-vars


  onComponentAdded(_comp) {} // eslint-disable-next-line @typescript-eslint/no-unused-vars


  onComponentRemoved(_comp) {}

  onInit() {
    if (!this.scene) return;
    this.sceneRef = this.scene;
    this.sceneConfig = this.sceneRef.config;
    this.initEventHandlers();
    let params = this.sceneConfig.get('params');
    const depends = this.sceneConfig.get('depends');
    const screenSize = this.sceneConfig.get('screenSize');
    const resolutionType = this.sceneConfig.get('resolutionType'); // --- for test


    if (params) {
      const result = TemplateUtils.constructWidgetsFromConfig(params, depends, this.sceneRef, [screenSize.x, screenSize.y], resolutionType);

      if (result) {
        [this.rootWidget, this.renderWidgets] = result;
        this.initTemplateDuration = TemplateUtils.getRootWidgetDuration(this.rootWidget);
      }
    } else {
      console.error('AMAZINGTEMPLATE', 'constructWidgetsFromConfig parameters error');
    }
  }

  onStart() {
    if (Amaz.DebugInstance !== undefined && Array.isArray(Amaz.DebugInstance)) {
      Amaz.DebugInstance.push(this);
    } else {
      Amaz.DebugInstance = [];
      Amaz.DebugInstance.push(this);
    }
  }

  onUpdate() {
    var _a, _b, _c;

    const timestamp = (_a = this.sceneConfig) === null || _a === void 0 ? void 0 : _a.get('timestamp');
    (_b = this.rootWidget) === null || _b === void 0 ? void 0 : _b.onUpdate(timestamp);
    (_c = this.renderWidgets) === null || _c === void 0 ? void 0 : _c.forEach(widget => {
      widget === null || widget === void 0 ? void 0 : widget.onUpdate(timestamp);
    });
  }

  onEvent(event) {
    var _a;

    const amazEvent = event;

    if (amazEvent.type == TemplateEventType.layerOperation) {
      (_a = this.sceneEventHandler) === null || _a === void 0 ? void 0 : _a.fire(amazEvent.args.get(0), amazEvent.args);
    }
  }

  onDestroy() {
    this.scene = undefined;
    this.rootWidget = undefined;
    this.renderWidgets = undefined;
    this.sceneEventHandler = undefined;
  }

  getParameters(parameters) {
    if (this.scene && this.rootWidget && this.renderWidgets) {
      return TemplateUtils.getWidgetParams(this.rootWidget, this.renderWidgets, parameters);
    }

    return '';
  }

  initEventHandlers() {
    this.sceneEventHandler = new EventHandler();

    const createLayerHandler = args => {
      if (this.scene && this.rootWidget && this.renderWidgets && args) {
        if (args.size() >= 7) {
          const layerName = args.get(1);
          const layerParams = args.get(2);
          const segmentStartTime = args.get(3);
          const segmentEndTime = args.get(4);
          const screenWidth = args.get(5);
          const screenHeight = args.get(6);
          const widget = TemplateUtils.createLayer(layerName, layerParams, segmentStartTime, segmentEndTime, this.initTemplateDuration, screenWidth, screenHeight, {
            mainScene: this.scene,
            rootWidget: this.rootWidget,
            renderWidgets: this.renderWidgets
          });

          if (widget !== null) {
            this.renderWidgets.push(widget);
          }
        } else {
          console.error('AMAZINGTEMPLATE', 'createLayer parameters error! createLayer failed!');
        }
      } else {
        console.error('AMAZINGTEMPLATE', 'createLayer scene, root or renderWidgets is null!');
      }
    };

    const removeLayerHandler = args => {
      if (this.scene && this.rootWidget && this.renderWidgets && args) {
        if (args.size() >= 2) {
          const layerName = args.get(1);
          this.renderWidgets = TemplateUtils.removeLayer(layerName, this.scene, this.rootWidget, this.renderWidgets);
        } else {
          console.error('AMAZINGTEMPLATE', 'removeLayer parameters error! removeLayer failed!');
        }
      }
    };

    const setTimeRangeHandler = args => {
      if (this.scene && this.rootWidget && this.renderWidgets && args) {
        if (args.size() >= 3) {
          const startTime = args.get(1);
          const endTime = args.get(2);
          TemplateUtils.setTemplateTimeRange(startTime, endTime, {
            mainScene: this.scene,
            rootWidget: this.rootWidget,
            renderWidgets: this.renderWidgets.filter(v => v != null)
          });
        } else {
          console.error('AMAZINGTEMPLATE', 'setTemplateTimeRange parameters error! setTemplateTimeRange failed!');
        }
      }
    };

    const setParametersHandler = args => {
      if (this.scene && this.rootWidget && this.renderWidgets && args) {
        if (args.size() >= 2) {
          const parametersStr = args.get(1);
          TemplateUtils.updateWidgetParams(this.rootWidget, this.renderWidgets, parametersStr);
        } else {
          console.error('AMAZINGTEMPLATE', 'setParameters parameters error! setParameters failed!');
        }
      }
    }; // resolution type is just for root widget


    const setResolutionTypeHandler = args => {
      if (this.scene && this.rootWidget && args) {
        if (args.size() >= 4) {
          const resolutionType = args.get(1);
          const screen_width = args.get(2);
          const screen_heght = args.get(3);
          TemplateUtils.setRootWidgetResolutionType(this.rootWidget, resolutionType, screen_width, screen_heght);
        } else {
          console.error('AMAZINGTEMPLATE', 'setResolutionType parameters error! setResolutionType failed!');
        }
      }
    };

    const setScreenSizeHandler = args => {
      if (this.scene && this.rootWidget && args) {
        if (args.size() >= 3) {
          const screenWidth = args.get(1);
          const screenHeight = args.get(2);
          TemplateUtils.setWidgetScreenSize(this.rootWidget, this.renderWidgets, screenWidth, screenHeight);
        } else {
          console.error('AMAZINGTEMPLATE', 'setResolutionType parameters error! setScreenSize failed!');
        }
      }
    };

    this.sceneEventHandler.on('createLayer', createLayerHandler, this);
    this.sceneEventHandler.on('removeLayer', removeLayerHandler, this);
    this.sceneEventHandler.on('setTimeRange', setTimeRangeHandler, this);
    this.sceneEventHandler.on('setParameters', setParametersHandler, this);
    this.sceneEventHandler.on('setResolutionType', setResolutionTypeHandler, this);
    this.sceneEventHandler.on('setScreenSize', setScreenSizeHandler, this);
  }

}
exports.main = Main;

exports.Main = Main;
//# sourceMappingURL=main.cjs.js.map
