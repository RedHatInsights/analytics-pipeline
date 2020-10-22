#!/usr/bin/env python3

import glob
import os

# install pillow for this ...
import Image
import numpy as np

# install scikit-image ...
from skimage.measure import compare_ssim

# install opencv-python for this ...
import cv2

import imutils


# https://www.pyimagesearch.com/2014/09/15/python-compare-two-images/
def mse(imageA, imageB):
	# the 'Mean Squared Error' between the two images is the
	# sum of the squared difference between the two images;
	# NOTE: the two images must have the same dimension
	err = np.sum((imageA.astype("float") - imageB.astype("float")) ** 2)
	err /= float(imageA.shape[0] * imageA.shape[1])
	
	# return the MSE, the lower the error, the more "similar"
	# the two images are
	return err


# https://www.pyimagesearch.com/2017/06/19/image-difference-with-opencv-and-python/
def make_diff(fileA, fileB):
# load the two input images
    imageA = cv2.imread(fileA)
    imageB = cv2.imread(fileB)
    # convert the images to grayscale
    grayA = cv2.cvtColor(imageA, cv2.COLOR_BGR2GRAY)
    grayB = cv2.cvtColor(imageB, cv2.COLOR_BGR2GRAY)

    (score, diff) = compare_ssim(grayA, grayB, full=True)
    diff = (diff * 255).astype("uint8")
    print("SSIM: {}".format(score))

    thresh = cv2.threshold(diff, 0, 255,
        cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)[1]
    cnts = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE)
    cnts = imutils.grab_contours(cnts)

    for c in cnts:
        # compute the bounding box of the contour and then draw the
        # bounding box on both input images to represent where the two
        # images differ
        (x, y, w, h) = cv2.boundingRect(c)
        cv2.rectangle(imageA, (x, y), (x + w, y + h), (0, 0, 255), 2)
        cv2.rectangle(imageB, (x, y), (x + w, y + h), (0, 0, 255), 2)


    cv2.imwrite('original.png', imageA)
    cv2.imwrite('modified.png', imageB)
    cv2.imwrite('diff.png', diff)
    cv2.imwrite('thresh.png', thresh)

    '''
    # show the output images
    cv2.imshow("Original", imageA)
    cv2.imshow("Modified", imageB)
    cv2.imshow("Diff", diff)
    cv2.imshow("Thresh", thresh)
    #cv2.waitKey(0)

    cv2.imwrite('original.png', imageA)
    cv2.imwrite('modified.png', imageB)
    cv2.imwrite('diff.png', diff)
    cv2.imwrite('thresh.png', thresh)
    '''


    #import epdb; epdb.st()

class ScreenshotDiffer:
    def __init__(self, a, b):
        self._a = a
        self._b = b
    
    def run(self):
        a_files = sorted(glob.glob('%s/*.png' % self._a))
        b_files = sorted(glob.glob('%s/*.png' % self._b))

        a = [os.path.basename(x) for x in a_files]
        b = [os.path.basename(x) for x in b_files]
        c = sorted(set(a + b))

        if a != b:
            for x in c:
                if x not in a:
                    print('%s does not have %s' % (self._a, x))
                if x not in b:
                    print('%s does not have %s' % (self._b, x))

        for x in c:
            Ia = Image.open(os.path.join(self._a, x))
            Ia = np.array(Ia)
            Ib = Image.open(os.path.join(self._b, x))
            Ib = np.array(Ib)

            this_mse = mse(Ia, Ib)
            print(this_mse)
            if this_mse > 0.0:
                print('%s differs from %s' % (os.path.join(self._a, x), os.path.join(self._b, x)))
                make_diff(os.path.join(self._a, x), os.path.join(self._b, x))
                import epdb; epdb.st()

        import epdb; epdb.st()


def main():
    SD = ScreenshotDiffer('screenshots', 'screenshots.changed')
    SD.run()


if __name__ == "__main__":
    main()