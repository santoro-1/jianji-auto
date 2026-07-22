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

var Amaz$5 = effect.Amaz;
var Color = Amaz$5.Color;
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
    const renderers = new Amaz$5.Vector();

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
      result = new Amaz$5.Vector4f(jsonArray[0], jsonArray[1], jsonArray[2], jsonArray[3]);
    }

    return result;
  };

  AmazUtils.CastJsonArray3fToAmazVector3f = function (jsonArray) {
    let result = null;

    if (jsonArray instanceof Array && jsonArray.length === 3) {
      result = new Amaz$5.Vector3f(jsonArray[0], jsonArray[1], jsonArray[2]);
    }

    return result;
  };

  AmazUtils.CastJsonArray2fToAmazVector2f = function (jsonArray) {
    let result = null;

    if (jsonArray instanceof Array && jsonArray.length === 2) {
      result = new Amaz$5.Vector2f(jsonArray[0], jsonArray[1]);
    }

    return result;
  };

  AmazUtils.CastJsonArrayToAmazVector = function (jsonArray) {
    const result = new Amaz$5.Vector();

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
    const fv = new Amaz$5.FloatVector();
    const ary = new Amaz$5.UInt16Vector();
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
    const quadMesh = new Amaz$5.Mesh();
    quadMesh.clearAfterUpload = true;
    quadMesh.vertices = fv;
    const posDesc = new Amaz$5.VertexAttribDesc();
    posDesc.semantic = Amaz$5.VertexAttribType.POSITION;
    const uvDesc = new Amaz$5.VertexAttribDesc();
    uvDesc.semantic = Amaz$5.VertexAttribType.TEXCOORD0;
    const vads = new Amaz$5.Vector();
    vads.pushBack(posDesc);
    vads.pushBack(uvDesc);
    quadMesh.vertexAttribs = vads;
    const aabb = new Amaz$5.AABB();
    aabb.min_x = -1.0;
    aabb.min_y = -1.0;
    aabb.min_z = 0.0;
    aabb.max_x = 1.0;
    aabb.max_y = 1.0;
    aabb.max_z = 0.0;
    quadMesh.boundingBox = aabb;
    const subMesh = new Amaz$5.SubMesh();
    ary.pushBack(0);
    ary.pushBack(1);
    ary.pushBack(2);
    ary.pushBack(3);
    subMesh.indices16 = ary;
    subMesh.primitive = Amaz$5.Primitive.TRIANGLE_FAN;
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

var Amaz$4 = effect.Amaz;
Amaz$4.Quaternionf;
Amaz$4.Vector2f;
var Vec3 = Amaz$4.Vector3f;

new Vec3(0.0, 0.0, 1.0);
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
const TEMPLATE_TAG$1 = 'AMAZINGTEMPLATE';

class CaptionWord {
  constructor(str, startTime, endTime, isKey, pageBreak) {
    // for letter find
    this.m_charIndexInPage = 0;
    this.m_string = str;
    this.m_startTime = startTime;
    this.m_endTime = endTime;
    this.m_isKey = isKey;
    this.m_pageBreak = pageBreak;
  }

  isLineBreak() {
    return this.m_string == "\n";
  }

  isPageBreak() {
    return this.isLineBreak() && this.m_pageBreak == true;
  }

  isSpace() {
    return this.m_string == " ";
  }

  isNormal() {
    return !this.isLineBreak() && !this.isSpace();
  }

  get startIndex() {
    return this.m_charIndexInPage;
  }

  get endIndex() {
    return this.m_charIndexInPage + this.m_string.length;
  }

}
class CaptionLine {
  constructor(words) {
    this.m_words = words; // set string

    this.m_string = "";

    for (let i = 0; i < this.m_words.length; i++) {
      this.m_string += this.m_words[i].m_string;
    } // set duration


    if (words.length > 0) {
      this.m_startTime = words[0].m_startTime;
      this.m_endTime = words[words.length - 1].m_endTime;
    } else {
      this.m_startTime = 0;
      this.m_endTime = 0;
    }
  }

  get startWord() {
    if (this.m_words.length > 0) return this.m_words[0];
    return null;
  }

  get endWord() {
    if (this.m_words.length > 0) return this.m_words[this.m_words.length - 1];
    return null;
  }

  get endCommonWord() {
    for (let i = this.m_words.length - 1; i >= 0; i--) {
      const word = this.m_words[i];

      if (!word.isLineBreak()) {
        return word;
      }
    }

    return null;
  }

  isPageBreak() {
    return this.endWord != null && this.endWord.isPageBreak();
  }

}
class CaptionPage {
  constructor(lines) {
    this.m_words = [];
    this.m_lines = [];
    this.m_utf16StartLetterIndex = -1;
    this.m_utf16EndLetterIndex = -1;
    this.m_lines = lines; // set string

    this.m_string = "";

    for (let i = 0; i < lines.length; i++) {
      this.m_string += lines[i].m_string;
      this.m_words = this.m_words.concat(lines[i].m_words);
    } // set duration


    if (lines.length > 0) {
      this.m_startTime = lines[0].m_startTime;
      this.m_endTime = lines[lines.length - 1].m_endTime;
    } else {
      this.m_startTime = 0;
      this.m_endTime = 0;
    }

    let index = 0;
    this.m_words.forEach(word => {
      // generate word.m_charIndexInPage
      word.m_charIndexInPage = index;
      index += word.m_string.length;
    });
  }

  get stringTrimEnd() {
    return this.m_string.trimEnd();
  }

  get startWord() {
    if (this.m_words.length > 0) return this.m_words[0];
    return null;
  }

  get endWord() {
    if (this.m_words.length > 0) return this.m_words[this.m_words.length - 1];
    return null;
  }

  get endCommonWord() {
    for (let i = this.m_words.length - 1; i >= 0; i--) {
      const word = this.m_words[i];

      if (!word.isLineBreak()) {
        return word;
      }
    }

    return null;
  }

  getCurrentWord(timeStamp) {
    timeStamp += this.m_startTime;
    if (timeStamp < this.m_startTime || timeStamp >= this.m_endTime) return null;

    for (let i = 0; i < this.m_words.length; i++) {
      if (this.m_words[i].isNormal() && timeStamp >= this.m_words[i].m_startTime && timeStamp < this.m_words[i].m_endTime) {
        return this.m_words[i];
      }
    } // there may be time gaps between adjacent words, so we return null here


    return null;
  }

  getCurrentLine(timeStamp) {
    timeStamp += this.m_startTime;
    if (timeStamp < this.m_startTime || timeStamp >= this.m_endTime) return null;

    for (let i = 0; i < this.m_lines.length; i++) {
      if (timeStamp >= this.m_lines[i].m_startTime && timeStamp < this.m_lines[i].m_endTime) {
        return this.m_lines[i];
      }
    }

    return null;
  }

  getCurrentCharIndex(timeStamp) {
    const currentWord = this.getCurrentWord(timeStamp);

    if (currentWord != null) {
      timeStamp += this.m_startTime;
      const progress = (timeStamp - currentWord.m_startTime) / (currentWord.m_endTime - currentWord.m_startTime);
      let index = Math.floor(currentWord.startIndex + (currentWord.endIndex - currentWord.startIndex) * progress);
      index = Math.min(Math.max(index, currentWord.startIndex), currentWord.endIndex - 1);
      return index;
    }

    console.error(TEMPLATE_TAG$1, "getCurrentCharIndex error", timeStamp);
    return null;
  }

}
class CaptionInfo {
  constructor() {
    this.m_caption_duration_info = null;
    this.m_string = "";
    this.m_startTime = 0;
    this.m_endTime = 0;
    this.m_pages = [];
    this.resetData();
  }

  get string() {
    return this.m_string;
  }

  get pages() {
    return this.m_pages;
  }

  set pages(value) {
    this.m_pages = value;
  }

  get caption_duration_info() {
    return this.m_caption_duration_info;
  }

  getPageIndex(timeStamp) {
    if (timeStamp < this.m_startTime || timeStamp >= this.m_endTime) return -1;
    if (this.m_pages.length == 0) return -1;

    for (let i = 0; i < this.m_pages.length; i++) {
      if (timeStamp >= this.m_pages[i].m_startTime && timeStamp < this.m_pages[i].m_endTime) {
        return i;
      } else if (timeStamp < this.m_pages[i].m_startTime && i > 0) {
        return i - 1;
      }
    }

    return -1;
  }

  getPage(timeStamp) {
    const index = this.getPageIndex(timeStamp);
    return index < 0 ? null : this.m_pages[index];
  }

  resetData() {
    this.m_caption_duration_info = null;
    this.m_string = "";
    this.m_startTime = 0;
    this.m_endTime = 0;
    this.m_pages = [];
  }

  setData(caption_duration_info) {
    if (caption_duration_info == null || Object.keys(caption_duration_info).length == 0) {
      this.resetData();
    }

    if (caption_duration_info == this.m_caption_duration_info) {
      return;
    }

    this.m_string = caption_duration_info.text;
    this.m_startTime = caption_duration_info.start_time / 1000;
    this.m_endTime = caption_duration_info.end_time / 1000;
    this.m_caption_duration_info = caption_duration_info;
  }

  updatePages() {
    if (this.m_caption_duration_info == null || this.m_caption_duration_info.words == null) {
      this.m_pages = [];
      return;
    } // generate words


    const words = [];

    for (let i = 0; i < this.m_caption_duration_info.words.length; i++) {
      const wordParam = this.m_caption_duration_info.words[i];
      let isKey = false;

      if ('is_key' in wordParam) {
        isKey = wordParam.is_key;
      }

      const word = new CaptionWord(wordParam.text, wordParam.start_time / 1000, wordParam.end_time / 1000, isKey, wordParam.new_page);
      words.push(word);
    } // generate lines


    const lines = [];
    let lineStart = 0;

    for (let i = 0; i < words.length; i++) {
      if (words[i].isLineBreak() || i == words.length - 1) {
        const lineWords = words.slice(lineStart, i + 1);
        const line = new CaptionLine(lineWords);
        lines.push(line);
        lineStart = i + 1;
      }
    } // generate pages


    this.m_pages = [];
    let pageStart = 0;

    for (let i = 0; i < lines.length; i++) {
      if (lines[i].isPageBreak() || i == lines.length - 1) {
        const pageLines = lines.slice(pageStart, i + 1);
        const page = new CaptionPage(pageLines);
        this.m_pages.push(page);
        pageStart = i + 1;
      }
    }
  }

  static getPageRange(captionPage) {
    if (captionPage.startWord != null && captionPage.endCommonWord != null) {
      return new SelectorRange(captionPage.startWord.startIndex, captionPage.endCommonWord.endIndex);
    } else {
      console.warn(TEMPLATE_TAG$1, "getPageRange warning");
      return new SelectorRange(0, 0);
    }
  }

  static getWordRange(time, captionPage) {
    const currentWord = captionPage.getCurrentWord(time);

    if (currentWord != null) {
      return new SelectorRange(currentWord.startIndex, currentWord.endIndex);
    } else {
      return new SelectorRange(0, 0);
    }
  }

  static getLineRange(time, captionPage) {
    const currentLine = captionPage.getCurrentLine(time);

    if (currentLine != null && currentLine.startWord != null && currentLine.endCommonWord != null) {
      return new SelectorRange(currentLine.startWord.startIndex, currentLine.endCommonWord.endIndex);
    } else {
      console.error(TEMPLATE_TAG$1, "getLineRange error", time);
      return new SelectorRange(0, 0);
    }
  }

  static getLetterRange(time, captionPage) {
    const index = captionPage.getCurrentCharIndex(time);

    if (index != null) {
      return new SelectorRange(index, index + 1);
    } else {
      console.error(TEMPLATE_TAG$1, "getLetterRange error", time);
      return new SelectorRange(0, 0);
    }
  }

}

/**
 * @class
 * @name Selector
 * @classdesc Selector
 * @description Selector
 * @author limingzhu.7
 * @sdk 15.7.0
 */

class SelectorRange {
  constructor(start, end) {
    this.m_startIndex = 0;
    this.m_endIndex = 0; // m_converted: if startIndex and endIndex are converted from string index to letter index

    this.m_converted = false;
    this.m_startIndex = start;
    this.m_endIndex = end;
  }

  empty() {
    return this.m_startIndex == 0 && this.m_endIndex == 0;
  }

}
class Selector {
  // the validation of selector and caption_duration_info should be checked on setting from outside.
  // so we can use them without re-checking
  // optionally, we can maintain a js-object in correspondence of caption_duration_info, so as to speedup
  static getSelectedRange(selector, time, captionPage) {
    if (!selector) {
      console.error(TEMPLATE_TAG$1, "Selector getSelectedRange selector is null!");
      return new SelectorRange(0, 0);
    }

    if (!captionPage) {
      console.error(TEMPLATE_TAG$1, "Selector getSelectedRange captionPage is null!");
      return new SelectorRange(0, 0);
    }

    let selectorUnit = 'word';

    if ('selector_unit' in selector) {
      selectorUnit = selector.selector_unit;
    }

    switch (selectorUnit) {
      case 'char':
        {
          return CaptionInfo.getLetterRange(time, captionPage);
        }

      case 'word':
        {
          return CaptionInfo.getWordRange(time, captionPage);
        }

      case 'line':
        {
          return CaptionInfo.getLineRange(time, captionPage);
        }

      case 'page':
        {
          return CaptionInfo.getPageRange(captionPage);
        }

      default:
        {
          console.error(TEMPLATE_TAG$1, "Selector getSelectedRange selectorUnit invalid!");
          return new SelectorRange(0, 0);
        }
    }
  }

}

/**
 *
 */
const Interpolation = {
  Linear: function (v, k) {
    const m = v.length - 1;
    const f = m * k;
    const i = Math.floor(f);
    const fn = Interpolation.Utils.Linear;

    if (k < 0) {
      return fn(v[0], v[1], f);
    }

    if (k > 1) {
      return fn(v[m], v[m - 1], m - f);
    }

    return fn(v[i], v[i + 1 > m ? m : i + 1], f - i);
  },
  Bezier: function (v, k) {
    let b = 0;
    const n = v.length - 1;
    const pw = Math.pow;
    const bn = Interpolation.Utils.Bernstein;

    for (let i = 0; i <= n; i++) {
      b += pw(1 - k, n - i) * pw(k, i) * v[i] * bn(n, i);
    }

    return b;
  },
  CatmullRom: function (v, k) {
    const m = v.length - 1;
    let f = m * k;
    let i = Math.floor(f);
    const fn = Interpolation.Utils.CatmullRom;

    if (v[0] === v[m]) {
      if (k < 0) {
        i = Math.floor(f = m * (1 + k));
      }

      return fn(v[(i - 1 + m) % m], v[i], v[(i + 1) % m], v[(i + 2) % m], f - i);
    } else {
      if (k < 0) {
        return v[0] - (fn(v[0], v[0], v[1], v[1], -f) - v[0]);
      }

      if (k > 1) {
        return v[m] - (fn(v[m], v[m], v[m - 1], v[m - 1], f - m) - v[m]);
      }

      return fn(v[i ? i - 1 : 0], v[i], v[m < i + 1 ? m : i + 1], v[m < i + 2 ? m : i + 2], f - i);
    }
  },
  Utils: {
    Linear: function (p0, p1, t) {
      return (p1 - p0) * t + p0;
    },
    Bernstein: function (n, i) {
      const fc = Interpolation.Utils.Factorial;
      return fc(n) / fc(i) / fc(n - i);
    },
    Factorial: function () {
      const a = [1];
      return function (n) {
        let s = 1;

        if (a[n]) {
          return a[n];
        }

        for (let i = n; i > 1; i--) {
          s *= i;
        }

        a[n] = s;
        return s;
      };
    }(),
    CatmullRom: function (p0, p1, p2, p3, t) {
      const v0 = (p2 - p0) * 0.5;
      const v1 = (p3 - p1) * 0.5;
      const t2 = t * t;
      const t3 = t * t2;
      return (2 * p1 - 2 * p2 + v0 + v1) * t3 + (-3 * p1 + 3 * p2 - 2 * v0 - v1) * t2 + v0 * t + p1;
    }
  }
};

/**
 * The Ease class provides a collection of easing functions for use with tween.js.
 */
const Easing = Object.freeze({
  Linear: Object.freeze({
    None(amount) {
      return amount;
    },

    In(amount) {
      return this.None(amount);
    },

    Out(amount) {
      return this.None(amount);
    },

    InOut(amount) {
      return this.None(amount);
    }

  }),
  Quadratic: Object.freeze({
    In(amount) {
      return amount * amount;
    },

    Out(amount) {
      return amount * (2 - amount);
    },

    InOut(amount) {
      if ((amount *= 2) < 1) {
        return 0.5 * amount * amount;
      }

      return -0.5 * (--amount * (amount - 2) - 1);
    }

  }),
  Cubic: Object.freeze({
    In(amount) {
      return amount * amount * amount;
    },

    Out(amount) {
      return --amount * amount * amount + 1;
    },

    InOut(amount) {
      if ((amount *= 2) < 1) {
        return 0.5 * amount * amount * amount;
      }

      return 0.5 * ((amount -= 2) * amount * amount + 2);
    }

  }),
  Quartic: Object.freeze({
    In(amount) {
      return amount * amount * amount * amount;
    },

    Out(amount) {
      return 1 - --amount * amount * amount * amount;
    },

    InOut(amount) {
      if ((amount *= 2) < 1) {
        return 0.5 * amount * amount * amount * amount;
      }

      return -0.5 * ((amount -= 2) * amount * amount * amount - 2);
    }

  }),
  Quintic: Object.freeze({
    In(amount) {
      return amount * amount * amount * amount * amount;
    },

    Out(amount) {
      return --amount * amount * amount * amount * amount + 1;
    },

    InOut(amount) {
      if ((amount *= 2) < 1) {
        return 0.5 * amount * amount * amount * amount * amount;
      }

      return 0.5 * ((amount -= 2) * amount * amount * amount * amount + 2);
    }

  }),
  Sinusoidal: Object.freeze({
    In(amount) {
      return 1 - Math.sin((1.0 - amount) * Math.PI / 2);
    },

    Out(amount) {
      return Math.sin(amount * Math.PI / 2);
    },

    InOut(amount) {
      return 0.5 * (1 - Math.sin(Math.PI * (0.5 - amount)));
    }

  }),
  Exponential: Object.freeze({
    In(amount) {
      return amount === 0 ? 0 : Math.pow(1024, amount - 1);
    },

    Out(amount) {
      return amount === 1 ? 1 : 1 - Math.pow(2, -10 * amount);
    },

    InOut(amount) {
      if (amount === 0) {
        return 0;
      }

      if (amount === 1) {
        return 1;
      }

      if ((amount *= 2) < 1) {
        return 0.5 * Math.pow(1024, amount - 1);
      }

      return 0.5 * (-Math.pow(2, -10 * (amount - 1)) + 2);
    }

  }),
  Circular: Object.freeze({
    In(amount) {
      return 1 - Math.sqrt(1 - amount * amount);
    },

    Out(amount) {
      return Math.sqrt(1 - --amount * amount);
    },

    InOut(amount) {
      if ((amount *= 2) < 1) {
        return -0.5 * (Math.sqrt(1 - amount * amount) - 1);
      }

      return 0.5 * (Math.sqrt(1 - (amount -= 2) * amount) + 1);
    }

  }),
  Elastic: Object.freeze({
    In(amount) {
      if (amount === 0) {
        return 0;
      }

      if (amount === 1) {
        return 1;
      }

      return -Math.pow(2, 10 * (amount - 1)) * Math.sin((amount - 1.1) * 5 * Math.PI);
    },

    Out(amount) {
      if (amount === 0) {
        return 0;
      }

      if (amount === 1) {
        return 1;
      }

      return Math.pow(2, -10 * amount) * Math.sin((amount - 0.1) * 5 * Math.PI) + 1;
    },

    InOut(amount) {
      if (amount === 0) {
        return 0;
      }

      if (amount === 1) {
        return 1;
      }

      amount *= 2;

      if (amount < 1) {
        return -0.5 * Math.pow(2, 10 * (amount - 1)) * Math.sin((amount - 1.1) * 5 * Math.PI);
      }

      return 0.5 * Math.pow(2, -10 * (amount - 1)) * Math.sin((amount - 1.1) * 5 * Math.PI) + 1;
    }

  }),
  Back: Object.freeze({
    In(amount) {
      const s = 1.70158;
      return amount === 1 ? 1 : amount * amount * ((s + 1) * amount - s);
    },

    Out(amount) {
      const s = 1.70158;
      return amount === 0 ? 0 : --amount * amount * ((s + 1) * amount + s) + 1;
    },

    InOut(amount) {
      const s = 1.70158 * 1.525;

      if ((amount *= 2) < 1) {
        return 0.5 * (amount * amount * ((s + 1) * amount - s));
      }

      return 0.5 * ((amount -= 2) * amount * ((s + 1) * amount + s) + 2);
    }

  }),
  Bounce: Object.freeze({
    In(amount) {
      return 1 - Easing.Bounce.Out(1 - amount);
    },

    Out(amount) {
      if (amount < 1 / 2.75) {
        return 7.5625 * amount * amount;
      } else if (amount < 2 / 2.75) {
        return 7.5625 * (amount -= 1.5 / 2.75) * amount + 0.75;
      } else if (amount < 2.5 / 2.75) {
        return 7.5625 * (amount -= 2.25 / 2.75) * amount + 0.9375;
      } else {
        return 7.5625 * (amount -= 2.625 / 2.75) * amount + 0.984375;
      }
    },

    InOut(amount) {
      if (amount < 0.5) {
        return Easing.Bounce.In(amount * 2) * 0.5;
      }

      return Easing.Bounce.Out(amount * 2 - 1) * 0.5 + 0.5;
    }

  }),

  generatePow(power = 4) {
    power = power < Number.EPSILON ? Number.EPSILON : power;
    power = power > 10000 ? 10000 : power;
    return {
      In(amount) {
        return Math.pow(amount, power);
      },

      Out(amount) {
        return 1 - Math.pow(1 - amount, power);
      },

      InOut(amount) {
        if (amount < 0.5) {
          return Math.pow(amount * 2, power) / 2;
        }

        return (1 - Math.pow(2 - amount * 2, power)) / 2 + 0.5;
      }

    };
  }

});

/**
 * Controlling groups of tweens
 *
 * Using the TWEEN singleton to manage your tweens can cause issues in large apps with many components.
 * In these cases, you may want to create your own smaller groups of tween
 */
class Group {
  constructor() {
    this._tweens = {};
    this._tweensAddedDuringUpdate = {};
  }

  getAll() {
    return Object.keys(this._tweens).map(tweenId => {
      return this._tweens[tweenId];
    });
  }

  removeAll() {
    this._tweens = {};
  }

  add(tween) {
    this._tweens[tween.getId()] = tween;
    this._tweensAddedDuringUpdate[tween.getId()] = tween;
  }

  remove(tween) {
    delete this._tweens[tween.getId()];
    delete this._tweensAddedDuringUpdate[tween.getId()];
  }

  update(time = 0, preserve = false) {
    let tweenIds = Object.keys(this._tweens);

    if (tweenIds.length === 0) {
      return false;
    } // Tweens are updated in "batches". If you add a new tween during an
    // update, then the new tween will be updated in the next batch.
    // If you remove a tween during an update, it may or may not be updated.
    // However, if the removed tween was added during the current batch,
    // then it will not be updated.


    while (tweenIds.length > 0) {
      this._tweensAddedDuringUpdate = {};

      for (let i = 0; i < tweenIds.length; i++) {
        const tween = this._tweens[tweenIds[i]];
        const autoStart = !preserve;

        if (tween && tween.update(time, autoStart) === false && !preserve) {
          delete this._tweens[tweenIds[i]];
        }
      }

      tweenIds = Object.keys(this._tweensAddedDuringUpdate);
    }

    return true;
  }

}

const mainGroup = new Group();

/**
 * Utils
 */
class Sequence {
  static nextId() {
    return Sequence._nextId++;
  }

}
Sequence._nextId = 0;

var Amaz$3 = effect.Amaz;
function bezier_3(t, p0, p1, p2, p3) {
  const it = 1 - t;
  return p0 * it * it * it + 3 * p1 * t * it * it + 3 * p2 * t * t * it + p3 * t * t * t;
}
class ColorRGBA {
  constructor(r, g, b, a) {
    this.r = 0.0;
    this.g = 0.0;
    this.b = 0.0;
    this.a = 0.0;
    this.r = r;
    this.g = g;
    this.b = b;
    this.a = a;
  }

  static normalizedToByte(f) {
    f = Math.max(f, 0.0);
    f = Math.min(f, 1.0);
    return Math.floor(f * 255.0 + 0.5);
  }

  static RGB2HSV(c) {
    // let lhsv = [];
    const r = ColorRGBA.normalizedToByte(c.r);
    const g = ColorRGBA.normalizedToByte(c.g);
    const b = ColorRGBA.normalizedToByte(c.b);
    const a = ColorRGBA.normalizedToByte(c.a);
    const max = Math.max(Math.max(r, g), b);
    const min = Math.min(Math.min(r, g), b);
    const v = max / 255.0;
    const s = max == 0 ? 0 : (max - min) / max;
    let h = 0;

    if (max == min) {
      h = 0;
    } else if (max == r && g >= b) {
      h = (g - b) * 60.0 / (max - min) + 0;
    } else if (max == r && g < b) {
      h = (g - b) * 60.0 / (max - min) + 360;
    } else if (max == g) {
      h = (b - r) * 60.0 / (max - min) + 120;
    } else if (max == b) {
      h = (r - g) * 60. / (max - min) + 240;
    }

    return new Amaz$3.Vector4f(h, s, v, a / 255.0);
  }

  static HSV2RGB(hsv) {
    const h = hsv.x;
    const s = hsv.y;
    const v = hsv.z;
    let r = 0,
        g = 0,
        b = 0; // let i = (int)Math.fmodf((h / 60.0), 6.0);

    const i = Math.floor(h / 60 % 6);
    const f = h / 60 - i;
    const p = v * (1 - s);
    const q = v * (1 - f * s);
    const t = v * (1 - (1 - f) * s);

    switch (i) {
      case 0:
        r = v;
        g = t;
        b = p;
        break;

      case 1:
        r = q;
        g = v;
        b = p;
        break;

      case 2:
        r = p;
        g = v;
        b = t;
        break;

      case 3:
        r = p;
        g = q;
        b = v;
        break;

      case 4:
        r = t;
        g = p;
        b = v;
        break;

      case 5:
        r = v;
        g = p;
        b = q;
        break;
    }

    return new ColorRGBA(Math.floor(r * 255) / 255.0, Math.floor(g * 255) / 255.0, Math.floor(b * 255) / 255.0, Math.floor(hsv.w * 255) / 255.0);
  }

  static castJsonArray4fToColorRGBA(jsonArray) {
    let result = null;

    if (jsonArray instanceof Array && jsonArray.length === 4) {
      result = new ColorRGBA(jsonArray[0], jsonArray[1], jsonArray[2], jsonArray[3]);
    }

    return result;
  }

  add(otherColor) {
    return new ColorRGBA(this.r + otherColor.r, this.g + otherColor.g, this.b + otherColor.b, this.a + otherColor.a);
  }

}

/**
 * Motion.js - Licensed under the MIT license
 * https://github.com/tweenjs/tween.js
 * ----------------------------------------------
 *
 * See https://github.com/tweenjs/tween.js/graphs/contributors for the full list of contributors.
 * Thank you all, you're awesome!
 */
var Amaz$2 = effect.Amaz;
class BezierInfo {
  constructor(isCubic, p0, p1, p2, p3) {
    this.isCubic = false;
    this.isCubic = isCubic;
    this.p0 = p0;
    this.p1 = p1;
    this.p2 = p2;
    this.p3 = p3;
  }

}
class Motion {
  constructor(_object, _isCubic = false, _group = mainGroup) {
    this._object = _object;
    this._isCubic = _isCubic;
    this._group = _group;
    this._isPaused = false;
    this._pauseStart = 0;
    this._valuesStart = {};
    this._valuesEnd = [];
    this._valuesStartRepeat = {};
    this._duration = [];
    this._isDynamic = false;
    this._initialRepeat = 0;
    this._repeat = 0;
    this._yoyo = false;
    this._isPlaying = false;
    this._reversed = false;
    this._delayTime = 0;
    this._startTime = 0;
    this._easingFunction = Easing.Linear.None;
    this._interpolationFunction = Interpolation.Linear; // eslint-disable-next-line

    this._chainedMotions = [];
    this._onStartCallbackFired = false;
    this._onEveryStartCallbackFired = false;
    this._id = Sequence.nextId();
    this._isChainStopped = false;
    this._propertiesAreSetUp = false;
    this._goToEnd = false;
  }

  setBezierInfo(p0, p1, p2, p3) {
    this._bezierInfo = [new BezierInfo(this._isCubic, p0, p1, p2, p3)];
    return this;
  }

  getObject() {
    return this._object;
  }

  getId() {
    return this._id;
  }

  setId(id) {
    this._id = id;
  }

  isPlaying() {
    return this._isPlaying;
  }

  isPaused() {
    return this._isPaused;
  }

  to(target, duration = 1000) {
    if (this._isPlaying) throw new Error('Can not call Motion.to() while Motion is already started or paused. Stop the Motion first.');
    this._valuesEnd = [target];
    this._propertiesAreSetUp = false;
    this._duration = [duration];
    return this;
  }

  seekTo(target, duration, bezierInfo) {
    if (this._isPlaying) throw new Error('Can not call Motion.seekTo() while Motion is already started or paused. Stop the Motion first.');
    if (target.length != duration.length) throw new Error('Can not call Motion.seekTo() because the length of target and duration not matching.');
    if (target.length != bezierInfo.length) throw new Error('Can not call Motion.seekTo() because the length of target and bezierInfo not matching.');
    this._valuesEnd = target;
    this._propertiesAreSetUp = false;
    this._duration = duration;
    this._bezierInfo = bezierInfo;
    return this;
  }

  duration(duration) {
    this._duration.fill(duration);

    return this;
  }

  durationAll(duration) {
    if (this._duration.length != duration.length) {
      throw new Error('Can not call Motion.durationAll() because the length of duration is not matching.');
    }

    this._duration = duration;
    return this;
  }

  dynamic(dynamic = false) {
    this._isDynamic = dynamic;
    return this;
  }

  start(time = 0, overrideStartingValues = false) {
    if (this._isPlaying) {
      return this;
    } // eslint-disable-next-line


    this._group && this._group.add(this);
    this._repeat = this._initialRepeat;

    if (this._reversed) {
      // If we were reversed (f.e. using the yoyo feature) then we need to
      // flip the motion direction back to forward.
      this._reversed = false;

      for (const property in this._valuesStartRepeat) {
        this._swapEndStartRepeatValues(property);

        this._valuesStart[property] = this._valuesStartRepeat[property];
      }
    }

    this._isPlaying = true;
    this._isPaused = false;
    this._onStartCallbackFired = false;
    this._onEveryStartCallbackFired = false;
    this._isChainStopped = false;
    this._startTime = time;
    this._startTime += this._delayTime;

    if (!this._propertiesAreSetUp || overrideStartingValues) {
      this._propertiesAreSetUp = true; // If dynamic is not enabled, clone the end values instead of using the passed-in end values.

      if (!this._isDynamic) {
        const tmp = [];

        for (const obj of this._valuesEnd) {
          const transformedObj = {};

          for (const prop in obj) {
            transformedObj[prop] = obj[prop];
          }

          tmp.push(transformedObj);
        }

        this._valuesEnd = tmp;
      }

      for (let i = 0; i < this._valuesEnd.length; i++) {
        this._setupProperties(this._object, this._valuesStart, this._valuesEnd[i], this._valuesStartRepeat, overrideStartingValues);
      }
    }

    return this;
  }

  startFromCurrentValues(time) {
    return this.start(time, true);
  }

  _setupProperties(_object, _valuesStart, _valuesEnd, _valuesStartRepeat, overrideStartingValues) {
    for (const property in _valuesEnd) {
      const startValue = _object[property];
      const startValueIsArray = Array.isArray(startValue);
      const propType = startValueIsArray ? 'array' : typeof startValue;
      let isInterpolationList = !startValueIsArray && Array.isArray(_valuesEnd[property]); // If `to()` specifies a property that doesn't exist in the source object,
      // we should not set that property in the object

      if (propType === 'undefined' || propType === 'function') {
        continue;
      } // Check if an Array was provided as property value


      if (isInterpolationList) {
        const endValues = _valuesEnd[property];

        if (endValues.length === 0) {
          continue;
        } // Handle an array of relative values.
        // Creates a local copy of the Array with the start value at the front
        // const temp = [startValue as number]


        const temp = [];

        for (let i = 0, l = endValues.length; i < l; i += 1) {
          const value = this._handleRelativeValue(startValue, endValues[i]);

          if (!(value instanceof ColorRGBA) && isNaN(value)) {
            isInterpolationList = false;
            console.warn('Found invalid interpolation list. Skipping.');
            break;
          }

          temp.push(value);
        }

        if (isInterpolationList) {
          // if (_valuesStart[property] === undefined) { // handle end values only the first time. NOT NEEDED? setupProperties is now guarded by _propertiesAreSetUp.
          _valuesEnd[property] = temp; // }
        }
      } // handle the deepness of the values


      if ((propType === 'object' || startValueIsArray) && startValue && !isInterpolationList && !(startValue instanceof ColorRGBA)) {
        _valuesStart[property] = startValueIsArray ? [] : {};
        const nestedObject = startValue;

        for (const prop in nestedObject) {
          _valuesStart[property][prop] = nestedObject[prop];
        } // TODO? repeat nested values? And yoyo? And array values?


        _valuesStartRepeat[property] = startValueIsArray ? [] : {};
        let endValues = _valuesEnd[property]; // If dynamic is not enabled, clone the end values instead of using the passed-in end values.

        if (!this._isDynamic) {
          const tmp = {};

          for (const prop in endValues) tmp[prop] = endValues[prop];

          _valuesEnd[property] = endValues = tmp;
        }

        this._setupProperties(nestedObject, _valuesStart[property], endValues, _valuesStartRepeat[property], overrideStartingValues);
      } else {
        // Save the starting value, but only once unless override is requested.
        if (typeof _valuesStart[property] === 'undefined' || overrideStartingValues) {
          _valuesStart[property] = startValue;
        }

        if (!startValueIsArray) {
          // eslint-disable-next-line
          // @ts-ignore FIXME?
          _valuesStart[property] *= 1.0; // Ensures we're using numbers, not strings
        }

        if (isInterpolationList) {
          // eslint-disable-next-line
          // @ts-ignore FIXME?
          _valuesStartRepeat[property] = _valuesEnd[property].slice().reverse();
        } else {
          _valuesStartRepeat[property] = _valuesStart[property] || 0;
        }
      }
    }
  }

  stop() {
    if (!this._isChainStopped) {
      this._isChainStopped = true;
      this.stopChainedMotions();
    }

    if (!this._isPlaying) {
      return this;
    } // eslint-disable-next-line


    this._group && this._group.remove(this);
    this._isPlaying = false;
    this._isPaused = false;

    if (this._onStopCallback) {
      this._onStopCallback(this._object);
    }

    return this;
  }

  end() {
    this._goToEnd = true;
    this.update(Infinity);
    return this;
  }

  pause(time = 0) {
    if (this._isPaused || !this._isPlaying) {
      return this;
    }

    this._isPaused = true;
    this._pauseStart = time; // eslint-disable-next-line

    this._group && this._group.remove(this);
    return this;
  }

  resume(time = 0) {
    if (!this._isPaused || !this._isPlaying) {
      return this;
    }

    this._isPaused = false;
    this._startTime += time - this._pauseStart;
    this._pauseStart = 0; // eslint-disable-next-line

    this._group && this._group.add(this);
    return this;
  }

  stopChainedMotions() {
    for (let i = 0, numChainedMotions = this._chainedMotions.length; i < numChainedMotions; i++) {
      this._chainedMotions[i].stop();
    }

    return this;
  }

  group(group = mainGroup) {
    this._group = group;
    return this;
  }

  delay(amount = 0) {
    this._delayTime = amount;
    return this;
  }

  repeat(times = 0) {
    this._initialRepeat = times;
    this._repeat = times;
    return this;
  }

  repeatDelay(amount) {
    this._repeatDelayTime = amount;
    return this;
  }

  yoyo(yoyo = false) {
    this._yoyo = yoyo;
    return this;
  }

  easing(easingFunction = Easing.Linear.None) {
    this._easingFunction = easingFunction;
    return this;
  }

  interpolation(interpolationFunction = Interpolation.Linear) {
    this._interpolationFunction = interpolationFunction;
    return this;
  } // eslint-disable-next-line


  chain(...motions) {
    this._chainedMotions = motions;
    return this;
  }

  onStart(callback) {
    this._onStartCallback = callback;
    return this;
  }

  onEveryStart(callback) {
    this._onEveryStartCallback = callback;
    return this;
  }

  onUpdate(callback) {
    this._onUpdateCallback = callback;
    return this;
  }

  onRepeat(callback) {
    this._onRepeatCallback = callback;
    return this;
  }

  onComplete(callback) {
    this._onCompleteCallback = callback;
    return this;
  }

  onStop(callback) {
    this._onStopCallback = callback;
    return this;
  }
  /**
   * @returns true if the motion is still playing after the update, false
   * otherwise (calling update on a paused motion still returns true because
   * it is still playing, just paused).
   */


  update(time = 0, autoStart = true) {
    var _a, _b, _c, _d;

    if (this._isPaused) return true;
    let accumulate = 0;
    let i = 0;
    const dis = time - this._startTime;

    for (i; i < this._duration.length; i++) {
      accumulate += this._duration[i];

      if (accumulate >= dis) {
        break;
      }
    }

    if (i == this._duration.length) {
      i--;
    }

    const duration = this._duration[i];
    const startTime = this._startTime + accumulate - duration;
    let property;
    let elapsed;
    const endTime = startTime + duration;

    if (!this._goToEnd && !this._isPlaying) {
      if (time > endTime) {
        return false;
      }

      if (autoStart) {
        this.start(time, true);
      }
    }

    this._goToEnd = false;

    if (time < this._startTime) {
      return true;
    }

    if (this._onStartCallbackFired === false) {
      if (this._onStartCallback) {
        this._onStartCallback(this._object);
      }

      this._onStartCallbackFired = true;
    }

    if (this._onEveryStartCallbackFired === false) {
      if (this._onEveryStartCallback) {
        this._onEveryStartCallback(this._object);
      }

      this._onEveryStartCallbackFired = true;
    }

    elapsed = (time - startTime) / duration;
    elapsed = duration === 0 || elapsed > 1 ? 1 : elapsed;

    const value = this._easingFunction(elapsed); // properties transformations


    if (i > 0 && ((_a = this._bezierInfo) === null || _a === void 0 ? void 0 : _a[i]) != undefined) {
      this._updateProperties(this._object, this._valuesEnd[i - 1], this._valuesEnd[i], value, (_b = this._bezierInfo) === null || _b === void 0 ? void 0 : _b[i]);
    } else if (((_c = this._bezierInfo) === null || _c === void 0 ? void 0 : _c[i]) != undefined) {
      this._updateProperties(this._object, this._valuesStart, this._valuesEnd[i], value, (_d = this._bezierInfo) === null || _d === void 0 ? void 0 : _d[i]);
    }

    if (this._onUpdateCallback) {
      this._onUpdateCallback(this._object, elapsed);
    }

    if (i < this._duration.length - 1) {
      return true;
    }

    if (elapsed === 1) {
      if (this._repeat > 0) {
        if (isFinite(this._repeat)) {
          this._repeat--;
        } // Reassign starting values, restart by making startTime = now


        for (property in this._valuesStartRepeat) {
          if (!this._yoyo && typeof this._valuesEnd[i][property] === 'string') {
            this._valuesStartRepeat[property] = // eslint-disable-next-line
            // @ts-ignore FIXME?
            this._valuesStartRepeat[property] + parseFloat(this._valuesEnd[i][property]);
          }

          if (this._yoyo) {
            this._swapEndStartRepeatValues(property);
          }

          this._valuesStart[property] = this._valuesStartRepeat[property];
        }

        if (this._yoyo) {
          this._reversed = !this._reversed;
        }

        if (this._repeatDelayTime !== undefined) {
          this._startTime = time + this._repeatDelayTime;
        } else {
          this._startTime = time + this._delayTime;
        }

        if (this._onRepeatCallback) {
          this._onRepeatCallback(this._object);
        }

        this._onEveryStartCallbackFired = false;
        return true;
      } else {
        if (this._onCompleteCallback) {
          this._onCompleteCallback(this._object);
        }

        for (let j = 0, numChainedMotions = this._chainedMotions.length; j < numChainedMotions; j++) {
          // Make the chained motions start exactly at the time they should,
          // even if the `update()` method was called way past the duration of the motion
          this._chainedMotions[j].start(this._startTime + duration, false);
        }

        this._isPlaying = false;
        return false;
      }
    }

    return true;
  }

  _updateProperties(_object, _valuesStart, _valuesEnd, value, bezierInfo) {
    for (const property in _valuesEnd) {
      // Don't update properties that do not exist in the source object
      if (_valuesStart[property] === undefined) {
        continue;
      }

      const start = _valuesStart[property] || 0;
      let end = _valuesEnd[property];
      const startIsArray = Array.isArray(_object[property]);
      const endIsArray = Array.isArray(end);
      const isInterpolationList = !startIsArray && endIsArray;

      if (isInterpolationList) {
        _object[property] = this._interpolationFunction(end, value);
      } else if (typeof end === 'object' && end && !(end instanceof ColorRGBA)) {
        // eslint-disable-next-line
        // @ts-ignore FIXME?
        this._updateProperties(_object[property], start, end, value);
      } else {
        // Parses relative end values with start as base (e.g.: +10, -3)
        end = this._handleRelativeValue(start, end); // Protect against non numeric properties.

        if (typeof end === 'number') {
          if (bezierInfo.isCubic && bezierInfo.p0 != undefined) {
            _object[property] = bezier_3(value, bezierInfo.p0, bezierInfo.p1, bezierInfo.p2, bezierInfo.p3);
          } else {
            // eslint-disable-next-line
            // @ts-ignore FIXME?
            _object[property] = start + (end - start) * value;
          }
        } else if (end instanceof ColorRGBA) {
          // eslint-disable-next-line
          // @ts-ignore FIXME?
          _object[property] = this.colorInterpolate(value, bezierInfo);
        } else {
          console.warn('Motion object property has something wrong');
        }
      }
    }
  }

  _handleRelativeValue(start, end) {
    if (typeof end !== 'string') {
      return end;
    }

    if (end.charAt(0) === '+' || end.charAt(0) === '-') {
      return start + parseFloat(end);
    }

    return parseFloat(end);
  }

  _swapEndStartRepeatValues(property) {
    const tmp = this._valuesStartRepeat[property];

    for (let i = 0; i < this._valuesEnd.length; i++) {
      const endValue = this._valuesEnd[i][property];

      if (typeof endValue === 'string') {
        this._valuesStartRepeat[property] = this._valuesStartRepeat[property] + parseFloat(endValue);
      } else {
        this._valuesStartRepeat[property] = this._valuesEnd[i][property];
      }

      this._valuesEnd[i][property] = tmp;
    }
  }

  colorInterpolate(value, bezierInfo) {
    const p0 = bezierInfo.p0;
    const p3 = bezierInfo.p3;
    const lhsv = ColorRGBA.RGB2HSV(new ColorRGBA(p0.r, p0.g, p0.b, 1.0));
    const rhsv = ColorRGBA.RGB2HSV(new ColorRGBA(p3.r, p3.g, p3.b, 1.0));

    if (!bezierInfo.isCubic) {
      const t = value; // use linear

      if (Math.abs(lhsv.x - rhsv.x) > 180) {
        if (lhsv.x < rhsv.x) rhsv.x -= 360;else lhsv.x -= 360;
      }

      const hsv = new Amaz$2.Vector4f(lhsv.x + (rhsv.x - lhsv.x) * t, lhsv.y + (rhsv.y - lhsv.y) * t, lhsv.z + (rhsv.z - lhsv.z) * t, lhsv.w + (rhsv.w - lhsv.w) * t);
      if (hsv.x < 0) hsv.x += 360;
      return ColorRGBA.HSV2RGB(hsv);
    }

    const p1 = bezierInfo.p1;
    const p2 = bezierInfo.p2;
    const lctrl = ColorRGBA.RGB2HSV(new ColorRGBA(p1.r, p1.g, p1.b, 1.0));
    const rctrl = ColorRGBA.RGB2HSV(new ColorRGBA(p2.r, p2.g, p2.b, 1.0));

    if (Math.abs(lhsv.x - rhsv.x) > 180) {
      if (lhsv.x < rhsv.x) {
        rhsv.x -= 360;
        rctrl.x -= 360;
      } else {
        lhsv.x -= 360;
        lctrl.x -= 360;
      }
    }

    const hsv = new Amaz$2.Vector4f(bezier_3(value, lhsv.x, lctrl.x, rctrl.x, rhsv.x), bezier_3(value, lhsv.y, lctrl.y, rctrl.y, rhsv.y), bezier_3(value, lhsv.z, lctrl.z, rctrl.z, rhsv.z), bezier_3(value, lhsv.w, lctrl.w, rctrl.w, rhsv.w));

    if (hsv.x < 0) {
      hsv.x += 360;
    }

    return ColorRGBA.HSV2RGB(hsv);
  }

}

const PAGE_POST_MOTION = new Group();
const LINE_POST_MOTION = new Group();
const WORD_POST_MOTION = new Group(); // motion after typesetting

const PAGE_MOTION = new Group();
const LINE_MOTION = new Group();
const WORD_MOTION = new Group();

class keyframeUnitInfo {
  constructor(v, t, it) {
    this.m_v = v;
    this.m_t = t;
    this.m_it = it;
    this.m_vti = 0.0;
    this.m_vto = 0.0;
    this.m_vi = v;
    this.m_vo = v;
  }

}

let IDX = -1;
const time_eps = 1e-5;
const CUBIC_BEZIER_EPSILON = 1e-3;
const ColorNames = ["tc", "bc", "sc", "oc", "tbc"];
class Keyframe {
  static getConvertedTime(word_start, word_end, anim_start, anim_end, time, delay) {
    const percent = (time - anim_start) / (anim_end - anim_start);
    return percent * (word_end - word_start) + delay;
  }

  static cubicBezier(x, tvOld, tvNew) {
    const vto = 1.0 * tvOld.m_vto / (tvNew.m_t - tvOld.m_t);
    const vti = 1.0 * tvNew.m_vti / (tvNew.m_t - tvOld.m_t) + 1.0;
    const p1 = [vto, 0];
    const p2 = [vti, 1];
    const a = 1.0 - 3.0 * p2[0] + 3.0 * p1[0];
    const b = 3.0 * p2[0] - 6. * p1[0];
    const c = 3.0 * p1[0];

    if (x < 0 || Math.abs(x) < time_eps) {
      return 0.0;
    }

    if (x > 1 || Math.abs(x - 1) < time_eps) {
      return 1.0;
    } // try 8 times iterator of Newton's method


    let t2 = x;

    for (let i = 0; i < 8; i++) {
      const x2 = ((a * t2 + b) * t2 + c) * t2 - x;

      if (Math.abs(x2) < CUBIC_BEZIER_EPSILON) {
        return t2;
      }

      const d2 = (a * 3.0 * t2 + b * 2.0) * t2 + c;

      if (Math.abs(d2) < time_eps) {
        break;
      }

      t2 = Math.max(0.0, Math.min(1.0, t2 - x2 / d2));
    } // fall back to bisection method


    let t0 = 0.0;
    let t1 = 1.0;

    while (t0 < t1 && Math.abs(t1 - t0) > time_eps) {
      const t2 = (t1 - t0) * 0.5 + t0;
      const x2 = ((a * t2 + b) * t2 + c) * t2;
      if (Math.abs(x2 - x) < CUBIC_BEZIER_EPSILON) return t2;
      if (x > x2) t0 = t2;else t1 = t2;
    } // failure


    if (t2 > 1.0) {
      t2 = 1.0;
    }

    return t2;
  }

  static createOneMotion(keyframes, updateFunc, _interp, motionContext, isFirst, group, propertyName) {
    if (isFirst) {
      ++IDX;
    }

    const motion = new Motion({
      v: keyframes[0].m_v,
      motionContext: motionContext,
      idx: IDX,
      propertyName: propertyName
    }, false, group).onUpdate(updateFunc);
    motion.interpolation(Interpolation.Linear);
    motion.easing(Easing.Linear.None);
    if (isFirst && keyframes[0].m_t > 0) motion === null || motion === void 0 ? void 0 : motion.delay(keyframes[0].m_t);
    const toList = [];
    const durationList = [];
    const bezierInfo = [];

    for (let i = 1; i < keyframes.length; i++) {
      toList.push({
        v: keyframes[i].m_v
      });
      durationList.push(keyframes[i].m_t - keyframes[i - 1].m_t);
      let isCubic = false;

      if (keyframes[i - 1].m_it === 'cubic' || keyframes[i].m_it === 'cubic') {
        isCubic = true;
      }

      bezierInfo.push(new BezierInfo(isCubic, keyframes[i - 1].m_v, keyframes[i - 1].m_vo, keyframes[i].m_vi, keyframes[i].m_v));
    }

    motion === null || motion === void 0 ? void 0 : motion.seekTo(toList, durationList, bezierInfo);
    return motion;
  }

  static isPostGroup(propertyName) {
    const postGroupProperties = ["sx", "sy", "px", "py", "rz"];
    return postGroupProperties.includes(propertyName);
  }

  static createMotionsForOneProperty(keyframe, motionContext, captionPage, propertyName, timeStamp) {
    const prop = keyframe.k[propertyName];
    const callback = Keyframe.setterMap[propertyName];

    if (prop == undefined) {
      console.error(TEMPLATE_TAG$1, "prop is undefined");
      return;
    }

    if (prop.length == 0) {
      console.error(TEMPLATE_TAG$1, "prop is empty");
      return;
    }

    const interp = Interpolation.Linear;
    let group = WORD_MOTION;
    const selectorUnit = motionContext.selector.selector_unit;
    let startTime = 0,
        endTime = 0;

    if (selectorUnit == 'word') {
      const cutrrentWord = captionPage.getCurrentWord(timeStamp);

      if (cutrrentWord != null) {
        startTime = cutrrentWord.m_startTime;
        endTime = cutrrentWord.m_endTime;
      }

      group = Keyframe.isPostGroup(propertyName) ? WORD_POST_MOTION : WORD_MOTION;
    } else if (selectorUnit == 'line') {
      const cutrrentLine = captionPage.getCurrentLine(timeStamp);

      if (cutrrentLine != null) {
        startTime = cutrrentLine.m_startTime;
        endTime = cutrrentLine.m_endTime;
      }

      group = Keyframe.isPostGroup(propertyName) ? LINE_POST_MOTION : LINE_MOTION;
    } else if (selectorUnit == 'page') {
      startTime = captionPage.m_startTime;
      endTime = captionPage.m_endTime;
      group = Keyframe.isPostGroup(propertyName) ? PAGE_POST_MOTION : PAGE_MOTION;
    }

    let animStartTime = 0,
        animEndTime = 0;
    const cutrrentWord = captionPage.getCurrentWord(timeStamp);

    if (cutrrentWord != null) {
      animStartTime = startTime - captionPage.m_startTime;
      animEndTime = endTime - captionPage.m_startTime;
    }

    const delay = animStartTime;
    const keyframes = [];
    let v = prop[0].v;

    if (prop[0].v instanceof Array && prop[0].v.length === 4) {
      v = ColorRGBA.castJsonArray4fToColorRGBA(prop[0].v);
    }

    keyframes.push(new keyframeUnitInfo(v, delay, prop[0].it));

    for (let i = 0; i < prop.length; i++) {
      const t = Keyframe.getConvertedTime(startTime, endTime, keyframe.s, keyframe.e, prop[i].t, delay);
      let v = prop[i].v;

      if (prop[i].v instanceof Array && prop[i].v.length === 4) {
        v = ColorRGBA.castJsonArray4fToColorRGBA(prop[i].v);
      }

      const keyframeUnit = new keyframeUnitInfo(v, t, prop[i].it);

      if (keyframeUnit.m_it === 'cubic') {
        keyframeUnit.m_vti = prop[i].vti;
        keyframeUnit.m_vto = prop[i].vto;

        if (ColorNames.includes(propertyName)) {
          // color
          const colorV = ColorRGBA.castJsonArray4fToColorRGBA(prop[i].v);
          const colorVi = ColorRGBA.castJsonArray4fToColorRGBA(prop[i].vi);
          const colorV0 = ColorRGBA.castJsonArray4fToColorRGBA(prop[i].v0);

          if (null !== colorV && null !== colorVi && null !== colorV0) {
            keyframeUnit.m_vi = colorV.add(colorVi);
            keyframeUnit.m_vo = colorV.add(colorV0);
          }
        } else {
          // number
          keyframeUnit.m_vi = prop[i].v + prop[i].vi;
          keyframeUnit.m_vo = prop[i].v + prop[i].vo;
        }
      }

      if (t - keyframes[keyframes.length - 1].m_t > time_eps) {
        keyframes.push(keyframeUnit);
      }
    }

    const convertedTime = Keyframe.getConvertedTime(animStartTime, animEndTime, keyframe.s, keyframe.e, keyframe.e, delay);

    if (convertedTime - keyframes[keyframes.length - 1].m_t > time_eps) {
      let v = prop[prop.length - 1].v;

      if (prop[prop.length - 1].v instanceof Array && prop[prop.length - 1].v.length === 4) {
        v = ColorRGBA.castJsonArray4fToColorRGBA(prop[prop.length - 1].v);
      }

      keyframes.push(new keyframeUnitInfo(v, convertedTime, prop[prop.length - 1].it));
    }

    Keyframe.createOneMotion(keyframes, callback, interp, motionContext, true, group, propertyName).start();
  }

  static sortFn(obj1, obj2) {
    const keys = Object.entries(Keyframe.setterMap);
    const index1 = keys.findIndex(e => e[0] === obj1.getObject().propertyName);
    const index2 = keys.findIndex(e => e[0] === obj2.getObject().propertyName);
    if (index1 < 0 || index2 < 0) return 0;else return index1 - index2;
  }

  static sortKeyframes(group) {
    const motions = group.getAll();

    if (motions.length > 1) {
      motions.sort(Keyframe.sortFn);
      group.removeAll();
      let idx = 0;
      motions.forEach(motion => {
        motion.setId(idx++);
        group.add(motion);
      });
    }
  }

  static createMotions(keyframe, motionContext, captionPage, timeStamp) {
    if (keyframe.k == undefined) {
      console.error(TEMPLATE_TAG$1, "keyframe.k is undefined");
      return;
    }

    const keyframe_time_factor = 0.000001;

    if ((keyframe.e - keyframe.s) * keyframe_time_factor < time_eps) {
      console.error(TEMPLATE_TAG$1, "keyframe time range too short");
      return;
    }

    for (const key in keyframe.k) Keyframe.createMotionsForOneProperty(keyframe, motionContext, captionPage, key, timeStamp);
  }

  static getNumberCallback(propertyName) {
    return function (obj) {
      const motionContext = obj.motionContext;
      const selectorRange = motionContext.selector.currentRange;
      const selectorUnit = obj.motionContext.selector.selector_unit;
      motionContext.callbackParams.values.push({
        name: propertyName,
        value: obj.v,
        start: selectorRange.m_startIndex,
        end: selectorRange.m_endIndex,
        overlayMode: motionContext.overlayMode,
        selectorUnit: selectorUnit
      });
    };
  }

  static getColorCallback(propertyName) {
    return function (obj) {
      const value = obj.v;
      const motionContext = obj.motionContext;
      const selectorRange = motionContext.selector.currentRange;
      const selectorUnit = obj.motionContext.selector.selector_unit;
      motionContext.callbackParams.values.push({
        name: propertyName,
        value: [value.r, value.g, value.b, value.a],
        start: selectorRange.m_startIndex,
        end: selectorRange.m_endIndex,
        overlayMode: motionContext.overlayMode,
        selectorUnit: selectorUnit
      });
    };
  }

}
Keyframe.setterMap = {
  // size (font size)
  s: Keyframe.getNumberCallback("s"),
  // transform
  // scale
  sx: Keyframe.getNumberCallback("sx"),
  sy: Keyframe.getNumberCallback("sy"),
  // rotation
  rz: Keyframe.getNumberCallback("rz"),
  // position
  px: Keyframe.getNumberCallback("px"),
  py: Keyframe.getNumberCallback("py"),
  // fill
  // fill color
  tc: Keyframe.getColorCallback("tc"),
  // fill alpha
  to: Keyframe.getNumberCallback("to"),
  // outline
  // outline color
  oc: Keyframe.getColorCallback("oc"),
  // outline opacity
  oo: Keyframe.getNumberCallback("oo"),
  // outline width
  ow: Keyframe.getNumberCallback("ow"),
  // shadow
  // shadow color
  sc: Keyframe.getColorCallback("sc"),
  // shadow opacity
  so: Keyframe.getNumberCallback("so"),
  // shadow angle
  sa: Keyframe.getNumberCallback("sa"),
  // shadow distance
  sd: Keyframe.getNumberCallback("sd"),
  // shadow smoothing
  ss: Keyframe.getNumberCallback("ss"),
  // shadow diffuse
  sdf: Keyframe.getNumberCallback("sdf"),
  // background
  // background color
  bc: Keyframe.getColorCallback("bc"),
  // background opacity
  bo: Keyframe.getNumberCallback("bo"),
  // background round radius
  br: Keyframe.getNumberCallback("br"),
  // background width
  bw: Keyframe.getNumberCallback("bw"),
  // background height
  bh: Keyframe.getNumberCallback("bh"),
  // background offset x
  bx: Keyframe.getNumberCallback("bx"),
  // background offset y
  by: Keyframe.getNumberCallback("by")
};

var Amaz$1 = effect.Amaz;
class InitValues {
  constructor(textComp, start = -1, end = -1) {
    this.selectStart = -1;
    this.selectEnd = -1;
    textComp.typeSettingDirty = true;
    textComp.forceTypeSetting();
    this.letters = textComp.letters.clone();
    this.backgrounds = textComp.backgrounds.clone();
    this.textStr = textComp.str;
    this.selectStart = start;
    this.selectEnd = end;
  }

}
class MotionContext {
  constructor(textComp, initValues, selector, overlayMode, callbackParams) {
    this.textComp = null;
    this.initValues = null;
    this.selector = null;
    this.callbackParams = null;
    this.textComp = textComp;
    this.initValues = initValues;
    this.selector = selector;
    this.overlayMode = overlayMode;
    this.callbackParams = callbackParams;
  }

}
class AnimationController {
  constructor(textComp) {
    this.m_captionInfo = new CaptionInfo();
    this.m_captionInfoDirty = false;
    this.m_currentCaptionPage = null;
    this.m_keyframeParams = null;
    this.m_keyFramesDirty = true;
    this.m_captionParams = {}; // If initialized to null, the assign function will report an error

    this.m_enabled = false;
    this.m_callbackParams = {};
    this.m_textComp = textComp;
    this.m_initValues = new InitValues(textComp);
  }

  get enabled() {
    return this.m_enabled;
  }

  set enabled(value) {
    this.m_enabled = value;
  }

  setCaptionDurationInfo(captionDurationInfo) {
    // update json data
    this.m_captionInfo.setData(captionDurationInfo);
    this.m_captionInfoDirty = true;
    this.m_enabled = true;
  }

  setKeyFrameParams(keyframeParams) {
    this.m_keyframeParams = keyframeParams;
    this.m_keyFramesDirty = true;
    this.m_enabled = true;
  }

  setCaptionParams(captionParams) {
    this.m_captionInfoDirty = true;
    this.m_keyFramesDirty = true;
    this.m_enabled = true; // special logic to reset m_captionParams

    if (Object.keys(captionParams).length == 0) {
      this.m_captionParams = {};
      return;
    } // set each attribute in captionParams


    Object.assign(this.m_captionParams, captionParams);
  }

  updateCaptionInfo() {
    if (!this.m_captionInfoDirty) return;
    this.m_captionInfoDirty = false; // disable splitLinePage from js, because the client side does it in consuming and production sides;
    // we keep thest commented code in case we perform it in effect side in future
    // // split lines, pages; update caption_duration_info
    // if (this.m_captionParams && this.m_captionInfo.caption_duration_info) {
    //     const utils = new Amaz.SwingTemplateUtils();
    //     const child = {
    //         "caption_params": this.m_captionParams,
    //         "text_params": {
    //             "caption_duration_info": this.m_captionInfo.caption_duration_info
    //         }
    //     };
    //     const outJsonStr = utils.splitLinePage(JSON.stringify(child), true);
    //     if (outJsonStr != "") {
    //         const caption_duration_info = JSON.parse(outJsonStr).caption_duration_info;
    //         this.m_captionInfo.setData(caption_duration_info);
    //     }
    // }
    // update pages

    this.m_captionInfo.updatePages();
  }

  resetAnimation() {
    this.m_keyFramesDirty = true;
  }

  findSelector(selectorId) {
    if (this.m_keyframeParams == null) {
      console.log(TEMPLATE_TAG$1, "findSelector keyframe_params is null");
      return null;
    }

    const selectors = this.m_keyframeParams.selectors;

    if (selectors == null) {
      console.log(TEMPLATE_TAG$1, "findSelector keyframe_params selectors is null");
      return null;
    }

    for (let i = 0; i < selectors.length; i++) {
      const selector = selectors[i];
      if (selector.id == selectorId) return selector;
    }

    return null;
  }

  refreshInitValues() {
    const range = this.m_textComp.getSelectRange();
    const VALID = 3;
    if (range.x == VALID) this.m_initValues = new InitValues(this.m_textComp, range.y, range.z);else this.m_initValues = new InitValues(this.m_textComp);
  }

  _sortKeyframes() {
    const groups = [PAGE_POST_MOTION, LINE_POST_MOTION, WORD_POST_MOTION, PAGE_MOTION, LINE_MOTION, WORD_MOTION];

    for (let i = 0; i < groups.length; i++) {
      const group = groups[i];
      Keyframe.sortKeyframes(group);
    }
  }

  updateKeyFrames(timeStamp) {
    PAGE_POST_MOTION.removeAll();
    LINE_POST_MOTION.removeAll();
    WORD_POST_MOTION.removeAll();
    PAGE_MOTION.removeAll();
    LINE_MOTION.removeAll();
    WORD_MOTION.removeAll();
    this.m_callbackParams = {};

    if (this.m_keyframeParams == null) {
      return;
    }

    const keyframes = this.m_keyframeParams.keyframes;

    if (keyframes == null) {
      return;
    }

    for (let i = 0; i < keyframes.length; i++) {
      const keyframe = keyframes[i]; // if there is no selector_id, keyframe is invalid, skip

      if (keyframe.selector_id == null) {
        continue;
      } // find selector


      const selector = this.findSelector(keyframe.selector_id);

      if (selector == null) {
        console.error(TEMPLATE_TAG$1, "keyframe_params error keyframe " + i + " selector is null");
        continue;
      } // overlayMode set


      let overlayMode = "over";
      if (["over", "add", "sub", "mul"].includes(keyframe.overlay_mode)) overlayMode = keyframe.overlay_mode;
      const motionContext = new MotionContext(this.m_textComp, this.m_initValues, selector, overlayMode, this.m_callbackParams);
      motionContext.callbackParams = this.m_callbackParams;
      if (this.m_currentCaptionPage != null) Keyframe.createMotions(keyframe, motionContext, this.m_currentCaptionPage, timeStamp);
    }

    this._sortKeyframes();
  }

  updateKeyword(currentPage) {
    if (currentPage == undefined || currentPage == null) {
      console.error(TEMPLATE_TAG$1, "updateKeyword currentPage is null");
    }

    if (this.m_captionParams == null || this.m_captionParams.keyword_rich_text == null) {
      return;
    }

    if (this.m_captionParams.enable_keyword == undefined || this.m_captionParams.enable_keyword == null) {
      return;
    }

    if (!this.m_captionParams.enable_keyword) {
      return;
    }

    const range = [];

    for (let i = 0; i < currentPage.m_words.length; i++) {
      if (currentPage.m_words[i].m_isKey) {
        range.push(currentPage.m_words[i].startIndex, currentPage.m_words[i].endIndex);
      }
    }

    if (range.length > 1) {
      this.m_textComp.applyTextStyle(this.m_captionParams.keyword_rich_text, range);
    }
  }

  get currentCaptionPage() {
    if (this.m_currentCaptionPage) return this.m_currentCaptionPage;else {
      return null;
    }
  }

  resetCurrentCaptionPage() {
    this.m_currentCaptionPage = null;
  }

  initFrame() {
    this.m_textComp.setString(this.m_initValues.textStr, false);
    const oldLetters = this.m_initValues.letters;
    const letters = this.m_textComp.letters;

    if (oldLetters.size() != letters.size()) {
      console.error(TEMPLATE_TAG$1, 'oldLetters.size() != letters.size()', oldLetters.size(), letters.size());
    }

    for (let i = 0; i < letters.size(); i++) {
      const letter = letters.get(i);
      const oldLetter = oldLetters.get(i);
      letter.letterStyle = oldLetter.letterStyle.clone();
    }

    this.m_textComp.forceTypeSetting();

    for (let i = 0; i < letters.size(); i++) {
      const letter = letters.get(i);
      const oldLetter = oldLetters.get(i);
      letter.position = oldLetter.position;
      letter.scale = oldLetter.scale;
      letter.rotate = oldLetter.rotate;
      letter.extraMatrix = oldLetter.extraMatrix;
    }

    const backgrounds = this.m_textComp.backgrounds;
    const oldBackgrounds = this.m_initValues.backgrounds;

    if (oldBackgrounds.size() == 0) {
      this.m_textComp.backgrounds.clear();
    } else {
      // reset the text background
      for (let i = 0; i < backgrounds.size(); i++) {
        const oldBg = oldBackgrounds.get(i);
        backgrounds.set(i, oldBg.clone());
      }
    } // update KeyFrames


    this.m_keyFramesDirty = true;
  } // convert char indices to letter indices (an emoji corresponds to 2 chars and 1 letter)
  // numbers should be in ascent order in charIndices
  // '\n' is skipped in determining both the charIndices and letterIndices


  static convertToLetterIndices(charIndices, lettersVec) {
    const letterIndices = [];
    if (charIndices.length == 0) return letterIndices;
    let utf16Size = 0;
    const letters = this.getLettersWithoutReturn(lettersVec);
    const letterSize = letters.length;
    let charPos = 0;
    let charIndex = charIndices[charPos];

    for (let i = 0; i < letterSize; i++) {
      const letter = letters[i];
      const curUtf16Size = utf16Size + letter.getUTF16Size();

      if (curUtf16Size > charIndex) {
        letterIndices.push(i);
        if (charPos >= charIndices.length - 1) break;
        charIndex = charIndices[++charPos];
      }

      utf16Size = curUtf16Size;
    }

    const count = charIndices.length - letterIndices.length;

    for (let i = 0; i < count; i++) letterIndices.push(letterSize);

    return letterIndices;
  }

  updateLetterIndices() {
    const startPageIndexInSegment = 0;
    const endPageIndexInSegment = this.m_captionInfo.pages.length - 1;
    const charIndices = [0];
    let charCount = 0;
    let returnCount = 0;

    for (let pageIndex = startPageIndexInSegment; pageIndex <= endPageIndexInSegment; pageIndex++) {
      const page = this.m_captionInfo.pages[pageIndex];
      charCount += page.m_string.length;

      for (let j = 0; j < page.m_string.length; j++) if (page.m_string[j] == '\n') returnCount++;

      charIndices.push(charCount - returnCount);
    }

    const letterIndices = AnimationController.convertToLetterIndices(charIndices, this.m_initValues.letters);

    for (let pageIndex = startPageIndexInSegment; pageIndex <= endPageIndexInSegment; pageIndex++) {
      const page = this.m_captionInfo.pages[pageIndex];
      page.m_utf16StartLetterIndex = letterIndices[pageIndex - startPageIndexInSegment];
      page.m_utf16EndLetterIndex = letterIndices[pageIndex - startPageIndexInSegment + 1];
    }
  }

  static getLettersWithoutReturn(letters) {
    const lettersWithoutReturn = [];

    for (let i = 0; i < letters.size();) {
      const letter = letters.get(i);

      if (letter.utf8 != '\n') {
        lettersWithoutReturn.push(letter);
      }

      i += letter.getUTF16Size();
    }

    return lettersWithoutReturn;
  }

  recoverLetters(str, startIndex = 0) {
    this.m_textComp.setString(str, false);
    const oldLetters = AnimationController.getLettersWithoutReturn(this.m_initValues.letters);
    const letters = AnimationController.getLettersWithoutReturn(this.m_textComp.letters);

    if (oldLetters.length < letters.length + startIndex) {
      console.error(TEMPLATE_TAG$1, 'without returns, oldLetters.length < letters.length + startIndex', oldLetters.length, letters.length, startIndex);
    }

    for (let i = 0; i < letters.length; i++) {
      const letter = letters[i];
      const oldLetter = oldLetters[i + startIndex];
      letter.letterStyle = oldLetter.letterStyle.clone();
    }
  }

  switchPage(currentPage) {
    this.m_currentCaptionPage = currentPage;
    this.updateLetterIndices();

    if (this.m_currentCaptionPage.m_utf16StartLetterIndex < 0) {
      console.error(TEMPLATE_TAG$1, 'utf16StartLetterIndex < 0');
      return;
    }

    this.recoverLetters(this.m_currentCaptionPage.stringTrimEnd, this.m_currentCaptionPage.m_utf16StartLetterIndex);
  } // timeStamp: time stamp in segment, in seconds


  update(timeStamp) {
    if (!this.m_enabled) return timeStamp;
    this.updateCaptionInfo(); // get current page by the timeStamp

    const currentPage = this.m_captionInfo.getPage(timeStamp);
    let timeStampInPage = timeStamp;

    if (currentPage != null) {
      // update current timeStamp
      timeStampInPage = timeStamp - currentPage.m_startTime; // page changed

      this.switchPage(currentPage);
    }

    this.m_keyFramesDirty = true;

    if (this.m_keyframeParams != null) {
      if (this.m_keyFramesDirty == true) {
        this.m_keyFramesDirty = false;
        this.updateKeyFrames(timeStampInPage);
      } // selectors update


      const selectors = this.m_keyframeParams.selectors;

      if (selectors != null) {
        for (let i = 0; i < selectors.length; i++) {
          const selector = selectors[i];
          const range = Selector.getSelectedRange(selector, timeStampInPage, this.currentCaptionPage);
          selector.currentRange = range;
        }
      }
    }

    const swingTemplateUtils = new Amaz$1.SwingTemplateUtils();
    this.m_callbackParams.values = [];
    this.m_textComp.forceTypeSetting();
    PAGE_MOTION.update(timeStampInPage, true);
    LINE_MOTION.update(timeStampInPage, true);
    this.flushCallbackQueue(swingTemplateUtils);

    if (currentPage != null) {
      this.updateKeyword(currentPage);
      this.m_textComp.forceTypeSetting();
    }

    WORD_MOTION.update(timeStampInPage, true);
    this.flushCallbackQueue(swingTemplateUtils);
    this.m_textComp.forceTypeSetting();
    PAGE_POST_MOTION.update(timeStampInPage, true);
    LINE_POST_MOTION.update(timeStampInPage, true);
    WORD_POST_MOTION.update(timeStampInPage, true);
    this.flushCallbackQueue(swingTemplateUtils);
    return timeStampInPage;
  }

  flushCallbackQueue(swingTemplateUtils) {
    if (this.m_callbackParams.values.length > 0) {
      const jsonStr = JSON.stringify(this.m_callbackParams);
      swingTemplateUtils.captionSetParamsBatch(this.m_textComp, jsonStr);
      this.m_callbackParams.values = [];
    }
  }

  setSelectRange(start, end) {
    if (start >= 0 && end >= 0) {
      const textCmd = new Amaz$1.TextCommand();
      textCmd.type = 32;
      textCmd.iParam1 = start;
      textCmd.iParam2 = end;
      this.m_textComp.pushCommand(textCmd);
      this.m_textComp.forceFlushCommandQueue();
    }
  }

  postUpdate(timeStamp) {
    if (!this.m_enabled) return timeStamp;
    if (this.m_keyframeParams != null) this.initFrame();
    this.setSelectRange(this.m_initValues.selectStart, this.m_initValues.selectEnd);
    return timeStamp;
  }

  onTextChangeForScript() {
    this.resetAnimation();
    this.resetCurrentCaptionPage();
    this.refreshInitValues();
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
    this.m_animationController = null; // for bridging from ScriptSegment to TextSegment
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
   * create animation controller
   * @date 2024-01-11
   * @param {textComp: Amaz.Text} textComp
   */


  createAnimationController(textComp) {
    this.m_animationController = new AnimationController(textComp);
    this.m_animationController.enabled = true;
  }
  /**
   * set parameters for the bridging script
   * @date 2024-01-11
   * @param {parameters: string} parameters
   */


  setParametersForScript(parameters) {
    const jsonParam = JSON.parse(parameters);

    if ('children' in jsonParam) {
      const children = jsonParam.children;

      if (children instanceof Array) {
        for (let i = 0; i < children.length; i++) {
          const child = children[i];

          if (child && 'name' in child) {
            if ('text_params' in child) {
              const text_params = child.text_params;

              if (text_params && 'caption_duration_info' in text_params) {
                this.setCaptionDurationInfo(text_params.caption_duration_info);
              }
            }

            if ('keyframe_params' in child) {
              this.setKeyFrameParams(child.keyframe_params);
            }

            if ('caption_params' in child) {
              this.setCaptionParams(child.caption_params);
            }
          }
        }
      }
    }
  }
  /**
   * reset data for the bridging script
   * @date 2024-02-22
   */


  resetForScript() {
    const empty = JSON.parse('{}');
    this.setCaptionDurationInfo(empty);
    this.setKeyFrameParams(empty);
    this.setCaptionParams(empty);
    if (this.m_animationController != null) this.m_animationController.enabled = false;
  }
  /**
   * setCaptionDurationInfo
   * @date 2024-01-11
   * @param {captionDurationInfo: any} captionDurationInfo
   */


  setCaptionDurationInfo(captionDurationInfo) {
    if (this.m_animationController != null) {
      this.m_animationController.setCaptionDurationInfo(captionDurationInfo);
    }
  }
  /**
   * setKeyFrameParams
   * @date 2024-01-11
   * @param {keyframeParams: any} keyframeParams
   */


  setKeyFrameParams(keyframeParams) {
    if (this.m_animationController != null) {
      this.m_animationController.setKeyFrameParams(keyframeParams);
    }
  }
  /**
   * setCaptionParams
   * @date 2024-01-11
   * @param {captionParams: any} captionParams
   */


  setCaptionParams(captionParams) {
    if (this.m_animationController != null) {
      this.m_animationController.setCaptionParams(captionParams);
    }
  }
  /**
   * update animation controller
   * @date 2024-01-11
   * @param {timeStamp: number} timeStamp
   */


  updateAnimationController(timeStamp) {
    if (this.m_animationController != null) {
      this.m_animationController.update(timeStamp);
    }
  }
  /**
   * post update animation controller after rendering
   * @date 2024-02-22
   * @param {timeStamp: number} timeStamp
   */


  postUpdateForScript(timeStamp) {
    if (this.m_animationController != null) {
      this.m_animationController.postUpdate(timeStamp);
    }
  }
  /**
   * callback function called when text updated
   * @date 2024-02-22
   */


  onTextChangeForScript() {
    if (this.m_animationController != null) {
      this.m_animationController.onTextChangeForScript();
    }
  }
  /**
   * callback function called when text get AnimationController status
   * @date 2024-02-22
   */


  getAnimationControllerEnabled() {
    if (this.m_animationController != null) return this.m_animationController.enabled;
    return false;
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
      scene.sendEvent(event);
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
        scene.sendEvent(event);
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
        scene.sendEvent(event);
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
        scene.sendEvent(event);
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
      scene.sendEvent(event);
    });
  }

  removeLayer(layerName) {
    const event = new Amaz.Event();
    event.type = TemplateEventType.layerOperation;
    event.args.pushBack('removeLayer');
    event.args.pushBack(layerName);
    this.scenes.map(scene => {
      scene.sendEvent(event);
    });
  }

}

const template = Template;
 // # sourceMappingURL=index.js.map

exports.Template = Template;
exports.template = template;
//# sourceMappingURL=template.cjs.js.map
